# utilities for training different models for neural signal decoding
import os
import numpy as np
import pandas as pd
import random
import copy
import matplotlib.pyplot as plt
import torch
import torch.nn as nn
import torch.optim as optim
import torch.nn.functional as F
from sklearn.metrics import confusion_matrix

from utils.nn_utils import *
from utils.plots_utils import *

# random seed for reproducibility
seed = 18
random.seed(seed)
np.random.seed(seed)
torch.manual_seed(seed)

def train_nn_model(model, train_loader, valid_loader, test_loader, config, seed=None):
    """
    Train a neural network model using the provided data loaders and configuration.

    Parameters:
    - model: The neural network model to be trained.
    - train_loader: DataLoader for the training set.
    - valid_loader: DataLoader for the validation set.
    - test_loader: DataLoader for the test set.
    - config: Dictionary containing training configuration parameters.
    - seed: Random seed for reproducibility (optional)
    
    Returns:
    - results_df: DataFrame containing the results of the training and evaluation.
    - losses_df: DataFrame containing the training and validation losses.
    """

    if seed is not None:
        # Set the random seed
        random.seed(seed)
        np.random.seed(seed)
        torch.manual_seed(seed)

    # moving model to the GPU (if available)
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    model.to(device)

    # training config
    num_epochs = config.get('num_epochs', 500)
    num_warmup = config.get('num_warmup', 100)
    min_num_epochs = config.get('min_num_epochs', 100)
    patience = config.get('patience', 20)
    learning_rate = config.get('learning_rate', 1e-4)
    weight_decay = config.get('weight_decay', 1e-3)
    scheduler_step_size = config.get('scheduler_step_size', 10)
    scheduler_gamma = config.get('scheduler_gamma', 0.1)
    log_epochs_training = config.get('log_epochs_training', True)
    log_plot = config.get('log_plot', True)
    scheduler = config.get('scheduler', 'steplr')

    noise_std = config.get('noise_std', 1)  # Standard deviation of noise
    noise_loss_weight = config.get('noise_loss_weight', 0.15)  # Weight for consistency term
    
    if log_epochs_training:
        log_epochs_num = config.get('log_epochs_num', 1)

    # Define the loss function and optimizer
    loss_fun = nn.CrossEntropyLoss()
    optimizer = optim.AdamW(model.parameters(), lr=learning_rate, weight_decay=weight_decay)

    # Define a learning rate scheduler
    if scheduler == 'steplr':
        scheduler = optim.lr_scheduler.StepLR(optimizer, step_size=scheduler_step_size, gamma=scheduler_gamma)
    elif scheduler == 'reduceonplateau':
        scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode='min', factor=0.5, patience=8)
    elif scheduler == 'cosine-warmup':
        scheduler = CosineSchedulerWithWarmup(optimizer, num_warmup_steps=num_warmup, num_training_steps=num_epochs, min_lr=2e-4)
    else:
        raise ValueError('Invalid scheduler type. Please provide one of the scheduler supported.')

    # Initialize lists to store losses
    train_losses = []
    train_accuracies = []
    valid_losses = []
    valid_accuracies = []

    # Training loop
    best_valid_loss = float('inf')
    best_valid_accuracy = 0
    best_valid_conf_matrix = None
    best_model = None
    no_improv_counter = 0  # Counter for early stopping
    axs = None # axes for training plots

    for epoch in range(1, num_epochs + 1):
        # Training phase
        model.train()

        train_loss = []
        train_accuracy = []

        for batch in train_loader:    
            optimizer.zero_grad()

            neural_features = batch['neural_features'].to(device, non_blocking=True)
            labels = batch['labels'].to(device, non_blocking=True)
            _, labels_class = torch.max(labels, 1)

            # Use noise-robust loss
            loss, output = noise_robust_loss(
                model, neural_features, labels_class, loss_fun, 
                noise_std=noise_std, noise_loss_weight=noise_loss_weight
            )

            loss.backward()
            optimizer.step()

            # Compute accuracy
            _, predicted = torch.max(output.data, 1)
            correct = (predicted == labels_class).sum().item()

            # store loss and accuracy
            train_loss.append(loss.item())
            train_accuracy.append(correct / len(labels))

        avg_train_loss = np.mean(train_loss)
        avg_train_accuracy = np.mean(train_accuracy)

        train_losses.append(avg_train_loss)
        train_accuracies.append(avg_train_accuracy)

        # Validation phase
        model.eval()
        valid_results = evaluate_model(model, valid_loader, loss_fun, device=device)

        valid_loss = valid_results['loss']
        valid_losses.append(valid_loss)
        valid_accuracy = valid_results['accuracy']
        valid_accuracies.append(valid_accuracy)         

        # early stopping logic (if applicable)
        if valid_loss < best_valid_loss:
            best_model = copy.deepcopy(model.state_dict())
            best_valid_loss = valid_loss
            best_valid_accuracy = valid_accuracy
            best_valid_conf_matrix = valid_results['conf_matrix']
            no_improv_counter = 0
        else:
            no_improv_counter += 1

            if epoch > min_num_epochs and no_improv_counter >= patience:
                break

        if log_epochs_training and epoch % log_epochs_num == 0:
            print(f'   Epoch {epoch}/{num_epochs}, Training Loss: {avg_train_loss:.4f}, Validation Loss: {valid_loss:.4f}, Validation Accuracy: {valid_accuracy:.2f}%')
            
            if log_plot:
                axs = plot_training_results(
                    train_losses=train_losses, 
                    valid_losses=valid_losses, 
                    valid_conf_matrix=best_valid_conf_matrix, 
                    axs=axs
                )   

        # Learning rate scheduler step
        if isinstance(scheduler, optim.lr_scheduler.ReduceLROnPlateau):
            scheduler.step(valid_loss)
        else:
            scheduler.step()

    # Load the best model
    model.load_state_dict(best_model)

    # Evaluate the model on the test set
    model.eval()
    test_results = evaluate_model(model, test_loader, loss_fun, device=device)

    # save losses to a dataframe
    results = {
        'num_epochs': epoch,
        'best_valid_loss': best_valid_loss,
        'best_valid_accuracy': best_valid_accuracy,
        'test_loss': test_results['loss'],
        'test_accuracy': test_results['accuracy']
    }

    results_df = pd.DataFrame(results, index=[0])

    losses_df = pd.DataFrame({
        'train_loss': train_losses,
        'valid_loss': valid_losses,
    })

    loss = test_results['loss']
    accuracy = test_results['accuracy']

    print(f'    Test loss: {loss:.5f} - Best valid accuracy: {best_valid_accuracy:.2f}% - Test accuracy: {accuracy:.2f}%')

    if log_plot:
        axs = plot_training_results(
            train_losses=train_losses, 
            valid_losses=valid_losses, 
            valid_conf_matrix=best_valid_conf_matrix, 
            test_conf_matrix=test_results['conf_matrix'],
            axs=axs,
            keep_open=True
        )

    return results_df, losses_df

def evaluate_model(model, data_loader, loss_fun, device=None):
    """
    Evaluate the model on the provided data loader.

    Parameters:
    - model: The neural network model to be evaluated.
    - data_loader: DataLoader for the dataset to evaluate.
    - loss_fun: The loss function to compute the loss.
    - device: The device to use for evaluation (optional, defaults to 'cuda' if available).
    Returns:
    - results: Dictionary containing the loss, accuracy, and confusion matrix.
    """
    if device is None:
        device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

    total_loss = []
    total_accuracy = []
    all_labels = []
    all_preds = []

    with torch.no_grad():
        for batch in data_loader:            
            neural_features = batch['neural_features'].to(device, non_blocking=True)
            labels = batch['labels'].to(device, non_blocking=True)
            _, labels_class = torch.max(labels, 1)

            output = model(neural_features)

            loss = loss_fun(output, labels_class)

            _, predicted = torch.max(output.data, 1)
            correct = (predicted == labels_class).sum().item()
            accuracy = correct / len(labels_class) * 100

            total_loss.append(loss.item())
            total_accuracy.append(accuracy)

            all_labels.extend(labels_class.cpu().numpy())
            all_preds.extend(predicted.cpu().numpy())

    total_loss = np.mean(total_loss)
    total_accuracy = np.mean(total_accuracy)
    conf_matrix = confusion_matrix(all_labels, all_preds)

    results = {
        'loss': total_loss,
        'accuracy': total_accuracy,
        'conf_matrix': conf_matrix
    }

    return results