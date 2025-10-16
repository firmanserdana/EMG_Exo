"""
Proportional Control Decoders for EMG-Based Hand Control
=========================================================

This module implements proportional control decoders for continuous EMG control.
Supports MLP (Multi-Layer Perceptron) and KNN (K-Nearest Neighbors) decoders
for regression-based proportional control of finger movements.

Features:
---------
- MLP Decoder: Neural network-based regressor for smooth proportional control
- KNN Decoder: Instance-based regressor for simple proportional control
- Per-finger control: Individual speed and force for each finger (flexion/extension)
- Whole-hand control: Combined speed and force for all fingers

Output Format:
--------------
For individual finger control:
    - thumb_flexion, thumb_extension
    - index_flexion, index_extension
    - middle_flexion, middle_extension
    - ring_flexion, ring_extension
    - pinky_flexion, pinky_extension

For whole-hand control:
    - hand_flexion (all fingers flex)
    - hand_extension (all fingers extend)

Each output is normalized to [0, 1] representing:
    - Speed: rate of movement
    - Force: strength/pressure of movement
"""

import numpy as np
import torch
import torch.nn as nn
import pickle
from sklearn.neighbors import KNeighborsRegressor
from sklearn.preprocessing import StandardScaler
from typing import Dict, Tuple, Optional


class MLPProportionalDecoder(nn.Module):
    """
    Multi-Layer Perceptron for proportional EMG control.
    
    Outputs continuous values for finger speed and force control.
    """
    
    def __init__(self, input_dim, hidden_dims=[256, 128, 64], 
                 output_dim=10, dropout=0.3, activation='relu'):
        """
        Initialize MLP decoder.
        
        Args:
            input_dim (int): Number of input features (EMG channels)
            hidden_dims (list): List of hidden layer dimensions
            output_dim (int): Number of output dimensions (e.g., 10 for 5 fingers x 2 directions)
            dropout (float): Dropout rate for regularization
            activation (str): Activation function ('relu', 'tanh', 'elu')
        """
        super(MLPProportionalDecoder, self).__init__()
        
        self.input_dim = input_dim
        self.output_dim = output_dim
        
        # Build network layers
        layers = []
        prev_dim = input_dim
        
        for hidden_dim in hidden_dims:
            layers.append(nn.Linear(prev_dim, hidden_dim))
            
            if activation == 'relu':
                layers.append(nn.ReLU())
            elif activation == 'tanh':
                layers.append(nn.Tanh())
            elif activation == 'elu':
                layers.append(nn.ELU())
            
            layers.append(nn.Dropout(dropout))
            prev_dim = hidden_dim
        
        # Output layer with sigmoid to ensure [0, 1] range
        layers.append(nn.Linear(prev_dim, output_dim))
        layers.append(nn.Sigmoid())
        
        self.network = nn.Sequential(*layers)
    
    def forward(self, x):
        """
        Forward pass through the network.
        
        Args:
            x (torch.Tensor): Input tensor (batch_size, seq_len, input_dim) or (batch_size, input_dim)
        
        Returns:
            torch.Tensor: Output proportional control values (batch_size, output_dim)
        """
        # Handle sequential input by taking the mean across time
        if len(x.shape) == 3:
            x = torch.mean(x, dim=1)
        
        return self.network(x)


class KNNProportionalDecoder:
    """
    K-Nearest Neighbors regressor for proportional EMG control.
    
    Simple instance-based learning for proportional control.
    """
    
    def __init__(self, n_neighbors=5, weights='distance', output_dim=10):
        """
        Initialize KNN decoder.
        
        Args:
            n_neighbors (int): Number of neighbors to consider
            weights (str): Weight function ('uniform' or 'distance')
            output_dim (int): Number of output dimensions
        """
        self.n_neighbors = n_neighbors
        self.weights = weights
        self.output_dim = output_dim
        
        # Initialize KNN regressor (multi-output)
        self.knn = KNeighborsRegressor(
            n_neighbors=n_neighbors,
            weights=weights,
            algorithm='auto',
            n_jobs=-1  # Use all available cores
        )
        
        # Scaler for input normalization
        self.scaler = StandardScaler()
        
        self.is_fitted = False
    
    def fit(self, X, y):
        """
        Fit the KNN model.
        
        Args:
            X (np.ndarray): Training features (n_samples, n_features)
            y (np.ndarray): Training targets (n_samples, output_dim)
        """
        # Normalize features
        X_scaled = self.scaler.fit_transform(X)
        
        # Fit KNN
        self.knn.fit(X_scaled, y)
        
        self.is_fitted = True
        
        print(f"KNN decoder fitted: {X.shape[0]} samples, {X.shape[1]} features, {y.shape[1]} outputs")
    
    def predict(self, X):
        """
        Predict proportional control values.
        
        Args:
            X (np.ndarray): Input features (n_samples, n_features)
        
        Returns:
            np.ndarray: Predicted proportional values (n_samples, output_dim)
        """
        if not self.is_fitted:
            raise ValueError("KNN decoder must be fitted before prediction")
        
        # Handle sequential input by taking mean
        if len(X.shape) == 3:
            X = np.mean(X, axis=1)
        
        # Normalize features
        X_scaled = self.scaler.transform(X)
        
        # Predict and clip to [0, 1]
        predictions = self.knn.predict(X_scaled)
        predictions = np.clip(predictions, 0.0, 1.0)
        
        return predictions
    
    def save(self, filepath):
        """Save the KNN decoder to file."""
        with open(filepath, 'wb') as f:
            pickle.dump({
                'knn': self.knn,
                'scaler': self.scaler,
                'n_neighbors': self.n_neighbors,
                'weights': self.weights,
                'output_dim': self.output_dim,
                'is_fitted': self.is_fitted
            }, f)
    
    def load(self, filepath):
        """Load the KNN decoder from file."""
        with open(filepath, 'rb') as f:
            data = pickle.load(f)
            self.knn = data['knn']
            self.scaler = data['scaler']
            self.n_neighbors = data['n_neighbors']
            self.weights = data['weights']
            self.output_dim = data['output_dim']
            self.is_fitted = data['is_fitted']


class ProportionalControlMapper:
    """
    Maps proportional decoder outputs to finger-specific control values.
    
    Handles both individual finger control and whole-hand control modes.
    """
    
    # Finger indices for mapping
    THUMB = 0
    INDEX = 1
    MIDDLE = 2
    RING = 3
    PINKY = 4
    
    # Control directions
    FLEXION = 0
    EXTENSION = 1
    
    def __init__(self, control_mode='individual_fingers', num_fingers=5):
        """
        Initialize the proportional control mapper.
        
        Args:
            control_mode (str): 'individual_fingers' or 'whole_hand'
            num_fingers (int): Number of fingers to control
        """
        self.control_mode = control_mode
        self.num_fingers = num_fingers
        
        if control_mode == 'individual_fingers':
            self.output_dim = num_fingers * 2  # 2 directions per finger
        elif control_mode == 'whole_hand':
            self.output_dim = 2  # Flexion and extension for all fingers
        else:
            raise ValueError(f"Unknown control mode: {control_mode}")
    
    def decode_output(self, proportional_values):
        """
        Decode proportional values into structured finger control.
        
        Args:
            proportional_values (np.ndarray): Raw decoder output (output_dim,)
        
        Returns:
            dict: Structured finger control values
                {
                    'thumb': {'flexion': float, 'extension': float},
                    'index': {'flexion': float, 'extension': float},
                    ...
                }
        """
        if self.control_mode == 'individual_fingers':
            return self._decode_individual_fingers(proportional_values)
        elif self.control_mode == 'whole_hand':
            return self._decode_whole_hand(proportional_values)
    
    def _decode_individual_fingers(self, values):
        """Decode individual finger control."""
        finger_names = ['thumb', 'index', 'middle', 'ring', 'pinky']
        
        result = {}
        for i, name in enumerate(finger_names[:self.num_fingers]):
            flex_idx = i * 2
            ext_idx = i * 2 + 1
            
            result[name] = {
                'flexion': float(values[flex_idx]),
                'extension': float(values[ext_idx]),
                'speed': float(values[flex_idx] + values[ext_idx]) / 2,  # Average for speed
                'force': float(max(values[flex_idx], values[ext_idx]))  # Max for force
            }
        
        return result
    
    def _decode_whole_hand(self, values):
        """Decode whole-hand control."""
        finger_names = ['thumb', 'index', 'middle', 'ring', 'pinky']
        
        flexion_val = float(values[0])
        extension_val = float(values[1])
        
        # Apply same values to all fingers
        result = {}
        for name in finger_names:
            result[name] = {
                'flexion': flexion_val,
                'extension': extension_val,
                'speed': (flexion_val + extension_val) / 2,
                'force': max(flexion_val, extension_val)
            }
        
        return result
    
    def to_unity_format(self, finger_control):
        """
        Convert finger control to Unity-compatible format.
        
        Args:
            finger_control (dict): Decoded finger control values
        
        Returns:
            dict: Unity-compatible format with normalized values
        """
        unity_data = {
            'control_type': 'proportional',
            'fingers': {}
        }
        
        for finger_name, control in finger_control.items():
            unity_data['fingers'][finger_name] = {
                'flexion_speed': control['flexion'],
                'extension_speed': control['extension'],
                'force': control['force']
            }
        
        return unity_data
    
    def to_esp32_format(self, finger_control):
        """
        Convert finger control to ESP32-compatible format.
        
        Args:
            finger_control (dict): Decoded finger control values
        
        Returns:
            dict: ESP32-compatible format with pressure and speed values
        """
        esp32_data = {
            'control_type': 'proportional',
            'fingers': {}
        }
        
        for finger_name, control in finger_control.items():
            # Convert normalized values to ESP32 ranges
            # Pressure: 0-100
            # Speed: 0-4 (discrete levels)
            
            flexion_pressure = int(control['flexion'] * 100)
            extension_pressure = int(control['extension'] * 100)
            speed_level = int(control['speed'] * 4)  # Map to 0-4 range
            
            esp32_data['fingers'][finger_name] = {
                'flexion_pressure': flexion_pressure,
                'extension_pressure': extension_pressure,
                'speed': speed_level,
                'force': int(control['force'] * 100)
            }
        
        return esp32_data


def load_proportional_decoder(decoder_path, decoder_type='mlp', device='cpu'):
    """
    Load a trained proportional decoder from file.
    
    Args:
        decoder_path (str): Path to saved decoder
        decoder_type (str): 'mlp' or 'knn'
        device (str): Device for PyTorch models
    
    Returns:
        decoder: Loaded decoder model
    """
    if decoder_type == 'mlp':
        # Load PyTorch model
        checkpoint = torch.load(decoder_path, map_location=device, weights_only=False)
        
        # Extract model configuration
        if isinstance(checkpoint, dict):
            model_state = checkpoint.get('model_state_dict', checkpoint)
            config = checkpoint.get('config', {})
            
            input_dim = config.get('input_dim', 64)
            hidden_dims = config.get('hidden_dims', [256, 128, 64])
            output_dim = config.get('output_dim', 10)
            dropout = config.get('dropout', 0.3)
            
            decoder = MLPProportionalDecoder(
                input_dim=input_dim,
                hidden_dims=hidden_dims,
                output_dim=output_dim,
                dropout=dropout
            )
            decoder.load_state_dict(model_state)
        else:
            decoder = checkpoint
        
        decoder.to(device)
        decoder.eval()
        
        return decoder
    
    elif decoder_type == 'knn':
        # Load KNN model
        decoder = KNNProportionalDecoder()
        decoder.load(decoder_path)
        
        return decoder
    
    else:
        raise ValueError(f"Unknown decoder type: {decoder_type}")
