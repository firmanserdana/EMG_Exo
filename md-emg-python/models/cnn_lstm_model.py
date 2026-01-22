"""
Hybrid CNN-LSTM Model for High-Density EMG Classification
==========================================================

Designed for 32-channel HD-sEMG grids to leverage spatial resolution while
maintaining fast inference for real-time control.

Architecture:
-------------
1. Spatial CNN Layer: Condenses 32 physical channels into ~8 "virtual muscle" features
   - Acts as a learned spatial filter
   - Reduces noise and extracts meaningful spatial patterns
   
2. Temporal LSTM Layer: Captures dynamic activation patterns
   - Distinguishes voluntary intent from artifacts
   - Learns the "wave" of muscle activation across the grid

Features:
---------
- Electrode dropout regularization (robustness to bad contacts)
- Optional channel attention mechanism
- Support for transfer learning (freeze spatial layers)
- Configurable for different grid sizes

References:
-----------
- CNN for spatial EMG filtering: doi.org/10.1002/eng2.12827
- LSTM for temporal EMG decoding: doi.org/10.3390/bioengineering11010077
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
from typing import Optional, Tuple, List


class ElectrodeDropout(nn.Module):
    """
    Electrode dropout layer for robustness training.
    
    Randomly zeros out entire electrode channels during training,
    forcing the model to be robust to bad contacts or cable noise.
    
    Parameters:
    -----------
    drop_prob : float
        Probability of dropping each electrode channel (default 0.1)
    drop_contiguous : bool
        If True, drops contiguous groups of electrodes (simulates grid detachment)
    """
    
    def __init__(self, drop_prob: float = 0.1, drop_contiguous: bool = False):
        super().__init__()
        self.drop_prob = drop_prob
        self.drop_contiguous = drop_contiguous
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Apply electrode dropout.
        
        Parameters:
        -----------
        x : torch.Tensor
            Input of shape (batch, seq_len, n_channels) or (batch, n_channels, seq_len)
        """
        if not self.training or self.drop_prob == 0:
            return x
        
        # Determine channel dimension
        if x.dim() == 3:
            batch_size = x.size(0)
            
            if x.size(1) > x.size(2):
                # Shape: (batch, seq_len, n_channels)
                n_channels = x.size(2)
                channel_dim = 2
            else:
                # Shape: (batch, n_channels, seq_len)
                n_channels = x.size(1)
                channel_dim = 1
        else:
            return x
        
        if self.drop_contiguous:
            # Drop contiguous groups (2-4 electrodes)
            mask = torch.ones(batch_size, n_channels, device=x.device)
            for b in range(batch_size):
                if torch.rand(1).item() < self.drop_prob * 3:  # Higher prob for group drop
                    group_size = torch.randint(2, 5, (1,)).item()
                    start = torch.randint(0, max(1, n_channels - group_size), (1,)).item()
                    mask[b, start:start+group_size] = 0
        else:
            # Independent channel dropout
            mask = (torch.rand(batch_size, n_channels, device=x.device) > self.drop_prob).float()
        
        # Scale to maintain expected value
        mask = mask / (1 - self.drop_prob + 1e-8)
        
        # Apply mask
        if channel_dim == 2:
            mask = mask.unsqueeze(1)  # (batch, 1, n_channels)
        else:
            mask = mask.unsqueeze(2)  # (batch, n_channels, 1)
        
        return x * mask


class SpatialConvBlock(nn.Module):
    """
    Spatial convolution block for extracting "virtual muscle" features.
    
    Uses 1D convolutions across channels to learn optimal spatial filters,
    similar to ICA or NMF but end-to-end learnable.
    
    Parameters:
    -----------
    in_channels : int
        Number of input EMG channels (e.g., 32)
    out_channels : int
        Number of virtual muscle features to extract (e.g., 8)
    kernel_size : int
        Temporal kernel size for initial feature extraction
    """
    
    def __init__(self, in_channels: int = 32, out_channels: int = 8, 
                 kernel_size: int = 5, dropout: float = 0.2):
        super().__init__()
        
        self.in_channels = in_channels
        self.out_channels = out_channels
        
        # Spatial mixing layer (learns channel combinations)
        self.spatial_mix = nn.Linear(in_channels, out_channels)
        
        # Temporal convolution on mixed channels
        self.temporal_conv = nn.Conv1d(
            out_channels, out_channels,
            kernel_size=kernel_size,
            padding=kernel_size // 2,
            groups=1  # Can use groups=out_channels for depthwise
        )
        
        self.bn = nn.BatchNorm1d(out_channels)
        self.dropout = nn.Dropout(dropout)
        self.activation = nn.GELU()
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass.
        
        Parameters:
        -----------
        x : torch.Tensor
            Input of shape (batch, seq_len, n_channels)
            
        Returns:
        --------
        torch.Tensor of shape (batch, seq_len, out_channels)
        """
        batch_size, seq_len, n_channels = x.shape
        
        # Spatial mixing: (batch, seq_len, in_ch) -> (batch, seq_len, out_ch)
        x = self.spatial_mix(x)
        x = self.activation(x)
        
        # Temporal conv: need (batch, channels, seq_len)
        x = x.transpose(1, 2)  # (batch, out_ch, seq_len)
        x = self.temporal_conv(x)
        x = self.bn(x)
        x = self.activation(x)
        x = self.dropout(x)
        
        # Back to (batch, seq_len, out_ch)
        x = x.transpose(1, 2)
        
        return x


class ChannelAttention(nn.Module):
    """
    Channel attention mechanism for weighting electrode importance.
    
    Learns which electrodes/features are most relevant for classification,
    helping handle electrode variability across sessions.
    """
    
    def __init__(self, n_channels: int, reduction: int = 4):
        super().__init__()
        
        self.avg_pool = nn.AdaptiveAvgPool1d(1)
        self.max_pool = nn.AdaptiveMaxPool1d(1)
        
        self.fc = nn.Sequential(
            nn.Linear(n_channels, n_channels // reduction, bias=False),
            nn.ReLU(),
            nn.Linear(n_channels // reduction, n_channels, bias=False)
        )
        
        self.sigmoid = nn.Sigmoid()
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Apply channel attention.
        
        Parameters:
        -----------
        x : torch.Tensor
            Input of shape (batch, seq_len, n_channels)
        """
        # Global pooling: (batch, seq_len, ch) -> (batch, ch)
        x_t = x.transpose(1, 2)  # (batch, ch, seq_len)
        
        avg_out = self.avg_pool(x_t).squeeze(-1)
        max_out = self.max_pool(x_t).squeeze(-1)
        
        # Channel attention weights
        avg_weights = self.fc(avg_out)
        max_weights = self.fc(max_out)
        
        weights = self.sigmoid(avg_weights + max_weights)
        
        # Apply attention
        return x * weights.unsqueeze(1)


class CNNLSTMModel(nn.Module):
    """
    Hybrid CNN-LSTM model for HD-sEMG classification.
    
    Optimized for 32-channel grids and real-time inference.
    
    Parameters:
    -----------
    input_channels : int
        Number of input EMG channels (default 32)
    virtual_channels : int
        Number of virtual muscle features from CNN (default 8)
    hidden_size : int
        LSTM hidden size (default 64)
    num_layers : int
        Number of LSTM layers (default 1)
    num_classes : int
        Number of output classes (default 3: rest, close, open)
    use_attention : bool
        Whether to use channel attention (default True)
    electrode_dropout : float
        Electrode dropout probability (default 0.1)
    dropout : float
        General dropout probability (default 0.3)
    """
    
    def __init__(
        self,
        input_channels: int = 32,
        virtual_channels: int = 8,
        hidden_size: int = 64,
        num_layers: int = 1,
        num_classes: int = 3,
        use_attention: bool = True,
        electrode_dropout: float = 0.1,
        dropout: float = 0.3
    ):
        super().__init__()
        
        self.input_channels = input_channels
        self.virtual_channels = virtual_channels
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        self.num_classes = num_classes
        self.use_attention = use_attention
        
        # Electrode dropout (robustness training)
        self.electrode_dropout = ElectrodeDropout(
            drop_prob=electrode_dropout,
            drop_contiguous=True
        )
        
        # Spatial CNN block (learned spatial filter)
        self.spatial_cnn = SpatialConvBlock(
            in_channels=input_channels,
            out_channels=virtual_channels,
            kernel_size=5,
            dropout=dropout
        )
        
        # Channel attention (optional)
        if use_attention:
            self.attention = ChannelAttention(virtual_channels, reduction=2)
        
        # Temporal LSTM
        self.lstm = nn.LSTM(
            input_size=virtual_channels,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0,
            bidirectional=False  # Unidirectional for real-time
        )
        
        # Classification head
        self.classifier = nn.Sequential(
            nn.Linear(hidden_size, hidden_size // 2),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_size // 2, num_classes)
        )
        
        # Hidden state storage for stateful inference
        self.h = None
        self.c = None
        
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    
    def forward(self, x: torch.Tensor, stateless: bool = True) -> torch.Tensor:
        """
        Forward pass.
        
        Parameters:
        -----------
        x : torch.Tensor
            Input of shape (batch, seq_len, n_channels)
        stateless : bool
            If True, reset hidden state each forward pass
            
        Returns:
        --------
        torch.Tensor of shape (batch, num_classes)
        """
        batch_size = x.size(0)
        
        # Electrode dropout (training only)
        x = self.electrode_dropout(x)
        
        # Spatial CNN: extract virtual muscle features
        x = self.spatial_cnn(x)  # (batch, seq_len, virtual_ch)
        
        # Channel attention
        if self.use_attention:
            x = self.attention(x)
        
        # LSTM: temporal dynamics
        if stateless or self.h is None:
            self.init_hidden(batch_size)
        
        lstm_out, (h, c) = self.lstm(x, (self.h, self.c))
        
        if not stateless:
            self.h = h.detach()
            self.c = c.detach()
        
        # Use last time step for classification
        last_output = lstm_out[:, -1, :]  # (batch, hidden_size)
        
        # Classification
        logits = self.classifier(last_output)
        
        return logits
    
    def init_hidden(self, batch_size: int):
        """Initialize hidden states."""
        self.h = torch.zeros(self.num_layers, batch_size, self.hidden_size).to(self.device)
        self.c = torch.zeros(self.num_layers, batch_size, self.hidden_size).to(self.device)
    
    def freeze_spatial(self):
        """Freeze spatial CNN layers for transfer learning."""
        for param in self.spatial_cnn.parameters():
            param.requires_grad = False
        print("Spatial CNN layers frozen for transfer learning")
    
    def unfreeze_spatial(self):
        """Unfreeze spatial CNN layers."""
        for param in self.spatial_cnn.parameters():
            param.requires_grad = True
        print("Spatial CNN layers unfrozen")
    
    def get_spatial_features(self, x: torch.Tensor) -> torch.Tensor:
        """Extract spatial features for visualization/analysis."""
        with torch.no_grad():
            x = self.spatial_cnn(x)
            if self.use_attention:
                x = self.attention(x)
        return x
    
    def get_trainable_params(self) -> int:
        """Get number of trainable parameters."""
        return sum(p.numel() for p in self.parameters() if p.requires_grad)


class CNNLSTMModelLight(nn.Module):
    """
    Lightweight version of CNN-LSTM for faster inference.
    
    Reduced complexity for deployment on resource-constrained systems.
    """
    
    def __init__(
        self,
        input_channels: int = 32,
        virtual_channels: int = 4,
        hidden_size: int = 32,
        num_classes: int = 3,
        dropout: float = 0.2
    ):
        super().__init__()
        
        # Simple spatial reduction
        self.spatial = nn.Sequential(
            nn.Linear(input_channels, virtual_channels),
            nn.ReLU(),
            nn.Dropout(dropout)
        )
        
        # Single layer LSTM
        self.lstm = nn.LSTM(
            input_size=virtual_channels,
            hidden_size=hidden_size,
            num_layers=1,
            batch_first=True
        )
        
        # Simple classifier
        self.classifier = nn.Linear(hidden_size, num_classes)
        
        self.h = None
        self.c = None
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    
    def forward(self, x: torch.Tensor, stateless: bool = True) -> torch.Tensor:
        batch_size = x.size(0)
        
        # Spatial reduction
        x = self.spatial(x)
        
        # LSTM
        if stateless or self.h is None:
            self.h = torch.zeros(1, batch_size, 32).to(self.device)
            self.c = torch.zeros(1, batch_size, 32).to(self.device)
        
        lstm_out, (h, c) = self.lstm(x, (self.h, self.c))
        
        if not stateless:
            self.h = h.detach()
            self.c = c.detach()
        
        # Classify
        logits = self.classifier(lstm_out[:, -1, :])
        
        return logits


def create_cnn_lstm_model(config: dict) -> nn.Module:
    """
    Factory function to create CNN-LSTM model from config.
    
    Parameters:
    -----------
    config : dict
        Model configuration dictionary
        
    Returns:
    --------
    nn.Module
    """
    model_type = config.get('type', 'standard')
    
    if model_type == 'light':
        return CNNLSTMModelLight(
            input_channels=config.get('input_channels', 32),
            virtual_channels=config.get('virtual_channels', 4),
            hidden_size=config.get('hidden_size', 32),
            num_classes=config.get('num_classes', 3),
            dropout=config.get('dropout', 0.2)
        )
    else:
        return CNNLSTMModel(
            input_channels=config.get('input_channels', 32),
            virtual_channels=config.get('virtual_channels', 8),
            hidden_size=config.get('hidden_size', 64),
            num_layers=config.get('num_layers', 1),
            num_classes=config.get('num_classes', 3),
            use_attention=config.get('use_attention', True),
            electrode_dropout=config.get('electrode_dropout', 0.1),
            dropout=config.get('dropout', 0.3)
        )
