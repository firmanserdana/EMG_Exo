"""
Training Script for Proportional Control Decoders
=================================================

This script trains MLP or KNN decoders for proportional EMG control.

Usage:
    python train_proportional_decoder.py --decoder mlp --config config/proportional_train.yaml
    python train_proportional_decoder.py --decoder knn --config config/proportional_train.yaml
"""

import argparse
import os
import yaml
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
import pickle
import time

from models.proportional_decoders import MLPProportionalDecoder, KNNProportionalDecoder
from utils.motor_unit_decomposition import get_mud_features


class ProportionalEMGDataset(Dataset):
    """Dataset for proportional EMG control"""
    
    def __init__(self, features, targets):
        """
        Args:
            features (np.ndarray): EMG features (n_samples, n_features)
            targets (np.ndarray): Target proportional values (n_samples, n_outputs)
        """
        self.features = torch.tensor(features, dtype=torch.float32)
        self.targets = torch.tensor(targets, dtype=torch.float32)
    
    def __len__(self):
        return len(self.features)
    
    def __getitem__(self, idx):
        return self.features[idx], self.targets[idx]


def load_training_data(config):
    """
    Load training data for proportional control.
    
    Args:
        config (dict): Configuration dictionary
    
    Returns:
        tuple: (X_train, y_train, X_val, y_val, X_test, y_test)
    """
    data_file = config['data_file']
    
    print(f"Loading data from: {data_file}")
    
    # Load data (format depends on your data structure)
    # This is a placeholder - adjust based on your actual data format
    if data_file.endswith('.npz'):
        data = np.load(data_file)
        emg_signals = data['emg']  # (n_samples, n_timepoints, n_channels)
        targets = data['targets']  # (n_samples, n_outputs)
    elif data_file.endswith('.pkl'):
        with open(data_file, 'rb') as f:
            data = pickle.load(f)
        emg_signals = data['emg']
        targets = data['targets']
    else:
        raise ValueError(f"Unsupported data format: {data_file}")
    
    print(f"Loaded EMG signals: {emg_signals.shape}")
    print(f"Loaded targets: {targets.shape}")
    
    # Extract features
    use_mud = config.get('use_motor_unit_decomposition', False)
    fsample = config.get('fsample', 2048)
    
    print(f"Extracting features (MUD={use_mud})...")
    
    features_list = []
    for i in range(len(emg_signals)):
        if i % 100 == 0:
            print(f"  Processing sample {i}/{len(emg_signals)}...")
        
        signal = emg_signals[i]
        features = get_mud_features(signal, fsample=fsample, use_mud=use_mud)
        features_list.append(features)
    
    features = np.array(features_list)
    
    print(f"Extracted features: {features.shape}")
    
    # Split data
    test_size = config.get('test_size', 0.2)
    val_size = config.get('val_size', 0.1)
    random_state = config.get('random_state', 42)
    
    # Split train/test
    X_train, X_test, y_train, y_test = train_test_split(
        features, targets, test_size=test_size, random_state=random_state
    )
    
    # Split train/validation
    X_train, X_val, y_train, y_val = train_test_split(
        X_train, y_train, test_size=val_size/(1-test_size), random_state=random_state
    )
    
    print(f"Train set: {X_train.shape}")
    print(f"Validation set: {X_val.shape}")
    print(f"Test set: {X_test.shape}")
    
    return X_train, y_train, X_val, y_val, X_test, y_test


def train_mlp_decoder(config, X_train, y_train, X_val, y_val):
    """
    Train MLP proportional decoder.
    
    Args:
        config (dict): Configuration
        X_train, y_train, X_val, y_val: Training and validation data
    
    Returns:
        MLPProportionalDecoder: Trained model
    """
    print("\n" + "="*60)
    print("Training MLP Proportional Decoder")
    print("="*60)
    
    # Model parameters
    input_dim = X_train.shape[1]
    output_dim = y_train.shape[1]
    hidden_dims = config.get('hidden_dims', [256, 128, 64])
    dropout = config.get('dropout', 0.3)
    activation = config.get('activation', 'relu')
    
    # Training parameters
    batch_size = config.get('batch_size', 32)
    num_epochs = config.get('num_epochs', 100)
    learning_rate = config.get('learning_rate', 0.001)
    weight_decay = config.get('weight_decay', 1e-5)
    
    # Device
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Using device: {device}")
    
    # Create model
    model = MLPProportionalDecoder(
        input_dim=input_dim,
        hidden_dims=hidden_dims,
        output_dim=output_dim,
        dropout=dropout,
        activation=activation
    )
    model.to(device)
    
    print(f"Model created: {input_dim} -> {' -> '.join(map(str, hidden_dims))} -> {output_dim}")
    
    # Create datasets and dataloaders
    train_dataset = ProportionalEMGDataset(X_train, y_train)
    val_dataset = ProportionalEMGDataset(X_val, y_val)
    
    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False)
    
    # Loss function and optimizer
    criterion = nn.MSELoss()
    optimizer = optim.Adam(model.parameters(), lr=learning_rate, weight_decay=weight_decay)
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode='min', patience=5, factor=0.5)
    
    # Training loop
    best_val_loss = float('inf')
    patience_counter = 0
    early_stopping_patience = config.get('early_stopping_patience', 15)
    
    train_losses = []
    val_losses = []
    
    print(f"\nStarting training for {num_epochs} epochs...")
    
    for epoch in range(num_epochs):
        # Training phase
        model.train()
        train_loss = 0.0
        
        for batch_features, batch_targets in train_loader:
            batch_features = batch_features.to(device)
            batch_targets = batch_targets.to(device)
            
            # Forward pass
            outputs = model(batch_features)
            loss = criterion(outputs, batch_targets)
            
            # Backward pass
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            
            train_loss += loss.item() * len(batch_features)
        
        train_loss /= len(train_dataset)
        train_losses.append(train_loss)
        
        # Validation phase
        model.eval()
        val_loss = 0.0
        
        with torch.no_grad():
            for batch_features, batch_targets in val_loader:
                batch_features = batch_features.to(device)
                batch_targets = batch_targets.to(device)
                
                outputs = model(batch_features)
                loss = criterion(outputs, batch_targets)
                
                val_loss += loss.item() * len(batch_features)
        
        val_loss /= len(val_dataset)
        val_losses.append(val_loss)
        
        # Learning rate scheduling
        scheduler.step(val_loss)
        
        # Print progress
        if (epoch + 1) % 10 == 0 or epoch == 0:
            print(f"Epoch [{epoch+1}/{num_epochs}] - Train Loss: {train_loss:.6f}, Val Loss: {val_loss:.6f}")
        
        # Early stopping
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            patience_counter = 0
            # Save best model
            best_model_state = model.state_dict()
        else:
            patience_counter += 1
            if patience_counter >= early_stopping_patience:
                print(f"Early stopping at epoch {epoch+1}")
                break
    
    # Load best model
    model.load_state_dict(best_model_state)
    
    print(f"\nTraining completed!")
    print(f"Best validation loss: {best_val_loss:.6f}")
    
    return model


def train_knn_decoder(config, X_train, y_train, X_val, y_val):
    """
    Train KNN proportional decoder.
    
    Args:
        config (dict): Configuration
        X_train, y_train, X_val, y_val: Training and validation data
    
    Returns:
        KNNProportionalDecoder: Trained model
    """
    print("\n" + "="*60)
    print("Training KNN Proportional Decoder")
    print("="*60)
    
    # Model parameters
    output_dim = y_train.shape[1]
    n_neighbors = config.get('n_neighbors', 5)
    weights = config.get('weights', 'distance')
    
    print(f"Parameters: n_neighbors={n_neighbors}, weights={weights}")
    
    # Create model
    model = KNNProportionalDecoder(
        n_neighbors=n_neighbors,
        weights=weights,
        output_dim=output_dim
    )
    
    # Train (fit) model
    print("Fitting KNN model...")
    start_time = time.time()
    model.fit(X_train, y_train)
    fit_time = time.time() - start_time
    
    print(f"Training completed in {fit_time:.2f}s")
    
    # Evaluate on validation set
    val_predictions = model.predict(X_val)
    val_mse = np.mean((val_predictions - y_val) ** 2)
    
    print(f"Validation MSE: {val_mse:.6f}")
    
    return model


def evaluate_model(model, X_test, y_test, decoder_type='mlp'):
    """
    Evaluate trained model on test set.
    
    Args:
        model: Trained model
        X_test: Test features
        y_test: Test targets
        decoder_type: 'mlp' or 'knn'
    """
    print("\n" + "="*60)
    print("Evaluating Model on Test Set")
    print("="*60)
    
    if decoder_type == 'mlp':
        device = next(model.parameters()).device
        model.eval()
        
        with torch.no_grad():
            X_test_tensor = torch.tensor(X_test, dtype=torch.float32).to(device)
            predictions = model(X_test_tensor).cpu().numpy()
    else:
        predictions = model.predict(X_test)
    
    # Calculate metrics
    mse = np.mean((predictions - y_test) ** 2)
    mae = np.mean(np.abs(predictions - y_test))
    
    # Per-output metrics
    per_output_mse = np.mean((predictions - y_test) ** 2, axis=0)
    per_output_mae = np.mean(np.abs(predictions - y_test), axis=0)
    
    print(f"Test MSE: {mse:.6f}")
    print(f"Test MAE: {mae:.6f}")
    print(f"\nPer-output MSE: {per_output_mse}")
    print(f"Per-output MAE: {per_output_mae}")
    
    # Correlation per output
    correlations = []
    for i in range(y_test.shape[1]):
        corr = np.corrcoef(y_test[:, i], predictions[:, i])[0, 1]
        correlations.append(corr)
    
    print(f"\nPer-output correlations: {correlations}")
    print(f"Mean correlation: {np.mean(correlations):.4f}")
    
    return {
        'mse': mse,
        'mae': mae,
        'per_output_mse': per_output_mse,
        'per_output_mae': per_output_mae,
        'correlations': correlations
    }


def save_model(model, config, decoder_type='mlp', metrics=None):
    """Save trained model to file."""
    output_dir = config.get('output_dir', 'models-subjects/healthy')
    os.makedirs(output_dir, exist_ok=True)
    
    control_mode = config.get('proportional_control_mode', 'individual_fingers')
    output_file = os.path.join(output_dir, f'proportional_{decoder_type}_{control_mode}')
    
    if decoder_type == 'mlp':
        output_file += '.pth'
        
        # Save model with config and metrics
        save_dict = {
            'model_state_dict': model.state_dict(),
            'config': {
                'input_dim': model.input_dim,
                'output_dim': model.output_dim,
                'hidden_dims': config.get('hidden_dims', [256, 128, 64]),
                'dropout': config.get('dropout', 0.3),
                'activation': config.get('activation', 'relu')
            }
        }
        
        if metrics:
            save_dict['metrics'] = metrics
        
        torch.save(save_dict, output_file)
    
    else:  # knn
        output_file += '.pkl'
        model.save(output_file)
    
    print(f"\nModel saved to: {output_file}")


def main():
    parser = argparse.ArgumentParser(description='Train proportional control decoder')
    parser.add_argument('--decoder', type=str, required=True, choices=['mlp', 'knn'],
                       help='Decoder type to train')
    parser.add_argument('--config', type=str, required=True,
                       help='Path to training configuration file')
    args = parser.parse_args()
    
    # Load configuration
    with open(args.config, 'r') as f:
        config = yaml.safe_load(f)
    
    print("="*60)
    print("Proportional Decoder Training")
    print("="*60)
    print(f"Decoder type: {args.decoder}")
    print(f"Config file: {args.config}")
    
    # Load data
    X_train, y_train, X_val, y_val, X_test, y_test = load_training_data(config)
    
    # Train model
    if args.decoder == 'mlp':
        model = train_mlp_decoder(config, X_train, y_train, X_val, y_val)
    else:
        model = train_knn_decoder(config, X_train, y_train, X_val, y_val)
    
    # Evaluate model
    metrics = evaluate_model(model, X_test, y_test, decoder_type=args.decoder)
    
    # Save model
    save_model(model, config, decoder_type=args.decoder, metrics=metrics)
    
    print("\n" + "="*60)
    print("Training completed successfully!")
    print("="*60)


if __name__ == '__main__':
    main()
