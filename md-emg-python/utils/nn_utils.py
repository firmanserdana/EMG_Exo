import math
import torch
import torch.nn.functional as F
from torch.optim.lr_scheduler import LambdaLR
from torch import nn

def CosineSchedulerWithWarmup(optimizer, num_warmup_steps, num_training_steps, min_lr=1e-6):
    """
    Creates a schedule with a linear warmup followed by a cosine decay.
    """
    def lr_lambda(current_step):
        # 1) Warmup phase
        if current_step < num_warmup_steps:
            return float(current_step) / float(max(1, num_warmup_steps))

        # 2) Cosine decay phase
        progress = float(current_step - num_warmup_steps) / float(max(1, num_training_steps - num_warmup_steps))
        return max(min_lr, 0.5 * (1.0 + math.cos(math.pi * progress)))

    return LambdaLR(optimizer, lr_lambda)

def StepLRWithWarmup(optimizer, num_warmup_steps, step_size, gamma, last_epoch=-1):
    """
    Creates a schedule with a linear warmup followed by a StepLR decay.
    
    Warmup: linearly increases LR from 0 to the initial LR over `num_warmup_steps`
    Step decay: after warmup, every `step_size` steps, the LR is multiplied by `gamma`.
    """
    def lr_lambda(current_step):
        # Warmup phase: linear increase from 0 to 1.
        if current_step < num_warmup_steps:
            return float(current_step) / float(max(1, num_warmup_steps))
        # StepLR phase: calculate steps passed after warmup.
        else:
            steps_since_warmup = current_step - num_warmup_steps
            exponent = steps_since_warmup // step_size
            return gamma ** exponent

    return LambdaLR(optimizer, lr_lambda, last_epoch=last_epoch)

def noise_robust_loss(model, neural_features, labels_class, loss_fun, noise_std=0.01, noise_loss_weight=0.1):
    """
    Compute noise-robust loss with consistency regularization.
    
    Args:
        model: Neural network model
        neural_features: Input features
        labels_class: Ground truth labels (class indices)
        loss_fun: Base loss function (e.g., CrossEntropyLoss)
        noise_std: Standard deviation of Gaussian noise to add
        noise_loss_weight: Weight for the noise loss term

    Returns:
        total_loss: Combined loss with consistency regularization
    """
    # Standard prediction
    output_clean = model(neural_features)
    
    # Add noise to input features
    noise = torch.randn_like(neural_features) * noise_std
    neural_features_noisy = neural_features + noise
    
    # Prediction on noisy input
    output_noisy = model(neural_features_noisy)
    
    # Standard classification loss
    classification_loss = loss_fun(output_clean, labels_class)
    
    # Consistency loss: outputs should be similar for clean and noisy inputs
    consistency_loss = F.kl_div(
        F.softmax(output_clean, dim=1), 
        F.softmax(output_noisy, dim=1), 
        reduction='batchmean'
    )

    # Combined loss
    total_loss = classification_loss + noise_loss_weight * consistency_loss
    
    return total_loss, output_clean

def weights_init(layer):
    if isinstance(layer, nn.Conv2d):    
        nn.init.kaiming_normal_(layer.weight, mode='fan_out', nonlinearity='relu')    
    elif isinstance(layer, nn.ConvTranspose2d):
        nn.init.xavier_normal_(layer.weight)
        if layer.bias is not None:
            nn.init.normal_(layer.bias)
    elif isinstance(layer, nn.LSTM):
        for name, param in layer.named_parameters():
            if 'weight_ih' in name:
                nn.init.uniform_(param.data, -0.1, 0.1)
            elif 'weight_hh' in name:
                nn.init.orthogonal_(param.data)
            elif 'bias' in name:
                param.data.fill_(0)
                # Set forget gate bias to 1.0 for better gradient flow
                n = param.size(0)
                start, end = n // 4, n // 2
                param.data[start:end].fill_(1.0)                
    elif isinstance(layer, nn.BatchNorm2d):
        nn.init.ones_(layer.weight)
        nn.init.zeros_(layer.bias)
    elif isinstance(layer, nn.Linear):
        nn.init.zeros_(layer.bias)