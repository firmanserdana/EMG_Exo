"""
Transfer Learning Utilities for EMG Models
==========================================

Implements transfer learning strategies for fast patient calibration:

1. Pre-training on healthy subject data
2. Transfer learning with frozen spatial layers
3. Fine-tuning only the classification head

This reduces calibration time from hours to seconds by leveraging
learned spatial filters from healthy subjects.

References:
-----------
- Transfer learning for EMG: PMC8236575
"""

import os
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset
import numpy as np
from typing import Optional, Dict, Tuple, List
from pathlib import Path
import yaml
import pickle
from tqdm import tqdm


class TransferLearningTrainer:
    """
    Transfer learning trainer for EMG models.
    
    Supports:
    - Full training (pre-training on healthy data)
    - Transfer learning (freeze spatial, train classifier)
    - Fine-tuning (full model with lower LR for spatial)
    """
    
    def __init__(
        self,
        model: nn.Module,
        device: torch.device = None,
        config: Dict = None
    ):
        self.model = model
        self.device = device or torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.model.to(self.device)
        
        self.config = config or {}
        
        # Training history
        self.history = {
            'train_loss': [],
            'val_loss': [],
            'train_acc': [],
            'val_acc': []
        }
    
    def pretrain(
        self,
        train_data: np.ndarray,
        train_labels: np.ndarray,
        val_data: Optional[np.ndarray] = None,
        val_labels: Optional[np.ndarray] = None,
        epochs: int = 100,
        batch_size: int = 64,
        lr: float = 0.001,
        patience: int = 10
    ) -> Dict:
        """
        Pre-train model on healthy subject data.
        
        Parameters:
        -----------
        train_data : np.ndarray
            Training data of shape (n_samples, seq_len, n_channels)
        train_labels : np.ndarray
            Training labels of shape (n_samples,)
        val_data : np.ndarray, optional
            Validation data
        val_labels : np.ndarray, optional
            Validation labels
        epochs : int
            Number of training epochs
        batch_size : int
            Batch size
        lr : float
            Learning rate
        patience : int
            Early stopping patience
            
        Returns:
        --------
        dict with training history
        """
        print("\n" + "="*60)
        print("🎓 PRE-TRAINING on healthy subject data")
        print("="*60)
        
        # Create data loaders
        train_dataset = TensorDataset(
            torch.FloatTensor(train_data),
            torch.LongTensor(train_labels)
        )
        train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
        
        if val_data is not None:
            val_dataset = TensorDataset(
                torch.FloatTensor(val_data),
                torch.LongTensor(val_labels)
            )
            val_loader = DataLoader(val_dataset, batch_size=batch_size)
        else:
            val_loader = None
        
        # Full model training
        optimizer = optim.AdamW(self.model.parameters(), lr=lr, weight_decay=0.01)
        scheduler = optim.lr_scheduler.ReduceLROnPlateau(
            optimizer, mode='min', factor=0.5, patience=5
        )
        criterion = nn.CrossEntropyLoss()
        
        best_val_loss = float('inf')
        patience_counter = 0
        
        for epoch in range(epochs):
            # Training
            self.model.train()
            train_loss = 0.0
            train_correct = 0
            train_total = 0
            
            for batch_x, batch_y in train_loader:
                batch_x = batch_x.to(self.device)
                batch_y = batch_y.to(self.device)
                
                optimizer.zero_grad()
                outputs = self.model(batch_x)
                loss = criterion(outputs, batch_y)
                loss.backward()
                optimizer.step()
                
                train_loss += loss.item()
                _, predicted = outputs.max(1)
                train_total += batch_y.size(0)
                train_correct += predicted.eq(batch_y).sum().item()
            
            train_loss /= len(train_loader)
            train_acc = 100.0 * train_correct / train_total
            
            self.history['train_loss'].append(train_loss)
            self.history['train_acc'].append(train_acc)
            
            # Validation
            if val_loader:
                val_loss, val_acc = self._validate(val_loader, criterion)
                self.history['val_loss'].append(val_loss)
                self.history['val_acc'].append(val_acc)
                
                scheduler.step(val_loss)
                
                # Early stopping
                if val_loss < best_val_loss:
                    best_val_loss = val_loss
                    patience_counter = 0
                    self._save_best_model()
                else:
                    patience_counter += 1
                    if patience_counter >= patience:
                        print(f"\nEarly stopping at epoch {epoch+1}")
                        break
                
                if (epoch + 1) % 10 == 0:
                    print(f"Epoch {epoch+1}/{epochs} - "
                          f"Train Loss: {train_loss:.4f}, Acc: {train_acc:.1f}% | "
                          f"Val Loss: {val_loss:.4f}, Acc: {val_acc:.1f}%")
            else:
                if (epoch + 1) % 10 == 0:
                    print(f"Epoch {epoch+1}/{epochs} - "
                          f"Train Loss: {train_loss:.4f}, Acc: {train_acc:.1f}%")
        
        print(f"\n✓ Pre-training complete. Best val loss: {best_val_loss:.4f}")
        return self.history
    
    def transfer_learn(
        self,
        patient_data: np.ndarray,
        patient_labels: np.ndarray,
        epochs: int = 20,
        batch_size: int = 32,
        lr: float = 0.01,
        freeze_spatial: bool = True
    ) -> Dict:
        """
        Transfer learning with patient data.
        
        Freezes spatial CNN layers and trains only the classifier,
        enabling fast calibration with minimal patient data.
        
        Parameters:
        -----------
        patient_data : np.ndarray
            Patient calibration data (n_samples, seq_len, n_channels)
        patient_labels : np.ndarray
            Patient labels
        epochs : int
            Number of fine-tuning epochs
        batch_size : int
            Batch size
        lr : float
            Learning rate (higher than pre-training)
        freeze_spatial : bool
            Whether to freeze spatial CNN layers
            
        Returns:
        --------
        dict with training history
        """
        print("\n" + "="*60)
        print("🔄 TRANSFER LEARNING with patient data")
        print("="*60)
        print(f"   Patient samples: {len(patient_data)}")
        print(f"   Freeze spatial: {freeze_spatial}")
        
        # Freeze spatial layers
        if freeze_spatial and hasattr(self.model, 'freeze_spatial'):
            self.model.freeze_spatial()
        
        # Create data loader
        dataset = TensorDataset(
            torch.FloatTensor(patient_data),
            torch.LongTensor(patient_labels)
        )
        loader = DataLoader(dataset, batch_size=batch_size, shuffle=True)
        
        # Only train classifier parameters
        if freeze_spatial:
            params = [p for p in self.model.parameters() if p.requires_grad]
            print(f"   Trainable params: {sum(p.numel() for p in params)}")
        else:
            params = self.model.parameters()
        
        optimizer = optim.Adam(params, lr=lr)
        criterion = nn.CrossEntropyLoss()
        
        transfer_history = {'loss': [], 'acc': []}
        
        for epoch in range(epochs):
            self.model.train()
            total_loss = 0.0
            correct = 0
            total = 0
            
            for batch_x, batch_y in loader:
                batch_x = batch_x.to(self.device)
                batch_y = batch_y.to(self.device)
                
                optimizer.zero_grad()
                outputs = self.model(batch_x)
                loss = criterion(outputs, batch_y)
                loss.backward()
                optimizer.step()
                
                total_loss += loss.item()
                _, predicted = outputs.max(1)
                total += batch_y.size(0)
                correct += predicted.eq(batch_y).sum().item()
            
            avg_loss = total_loss / len(loader)
            acc = 100.0 * correct / total
            transfer_history['loss'].append(avg_loss)
            transfer_history['acc'].append(acc)
            
            print(f"   Epoch {epoch+1}/{epochs} - Loss: {avg_loss:.4f}, Acc: {acc:.1f}%")
        
        print(f"\n✓ Transfer learning complete. Final accuracy: {acc:.1f}%")
        return transfer_history
    
    def quick_calibrate(
        self,
        calibration_data: np.ndarray,
        calibration_labels: np.ndarray,
        n_epochs: int = 5
    ) -> float:
        """
        Quick calibration for clinical use.
        
        Minimal epochs for fast patient setup.
        
        Returns:
        --------
        Final accuracy percentage
        """
        print("\n⚡ QUICK CALIBRATION (clinical mode)")
        
        history = self.transfer_learn(
            calibration_data,
            calibration_labels,
            epochs=n_epochs,
            batch_size=16,
            lr=0.02,
            freeze_spatial=True
        )
        
        return history['acc'][-1]
    
    def _validate(self, val_loader, criterion) -> Tuple[float, float]:
        """Validate model on validation set."""
        self.model.eval()
        val_loss = 0.0
        correct = 0
        total = 0
        
        with torch.no_grad():
            for batch_x, batch_y in val_loader:
                batch_x = batch_x.to(self.device)
                batch_y = batch_y.to(self.device)
                
                outputs = self.model(batch_x)
                loss = criterion(outputs, batch_y)
                
                val_loss += loss.item()
                _, predicted = outputs.max(1)
                total += batch_y.size(0)
                correct += predicted.eq(batch_y).sum().item()
        
        return val_loss / len(val_loader), 100.0 * correct / total
    
    def _save_best_model(self):
        """Save best model checkpoint."""
        self._best_state = {k: v.cpu().clone() for k, v in self.model.state_dict().items()}
    
    def load_best_model(self):
        """Load best model from checkpoint."""
        if hasattr(self, '_best_state'):
            self.model.load_state_dict(self._best_state)
    
    def save_model(self, path: str):
        """Save model to file."""
        torch.save({
            'model_state_dict': self.model.state_dict(),
            'config': self.config,
            'history': self.history
        }, path)
        print(f"Model saved to {path}")
    
    def load_model(self, path: str):
        """Load model from file."""
        checkpoint = torch.load(path, map_location=self.device)
        self.model.load_state_dict(checkpoint['model_state_dict'])
        self.config = checkpoint.get('config', {})
        self.history = checkpoint.get('history', {})
        print(f"Model loaded from {path}")


def prepare_dynamic_training_data(
    static_data: np.ndarray,
    static_labels: np.ndarray,
    movement_data: np.ndarray,
    movement_labels: np.ndarray,
    balance: bool = True
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Combine static and movement data for dynamic training.
    
    Training with arm movement data teaches the model to recognize
    gestures even when shoulder muscles distort the signal.
    
    Parameters:
    -----------
    static_data : np.ndarray
        Data collected with arm stationary
    static_labels : np.ndarray
        Labels for static data
    movement_data : np.ndarray
        Data collected during arm movement (transport phase simulation)
    movement_labels : np.ndarray
        Labels for movement data
    balance : bool
        Whether to balance static/movement samples
        
    Returns:
    --------
    (combined_data, combined_labels)
    """
    if balance:
        # Balance to have equal static and movement samples
        n_static = len(static_data)
        n_movement = len(movement_data)
        
        if n_static > n_movement:
            # Subsample static data
            indices = np.random.choice(n_static, n_movement, replace=False)
            static_data = static_data[indices]
            static_labels = static_labels[indices]
        elif n_movement > n_static:
            # Subsample movement data
            indices = np.random.choice(n_movement, n_static, replace=False)
            movement_data = movement_data[indices]
            movement_labels = movement_labels[indices]
    
    combined_data = np.concatenate([static_data, movement_data], axis=0)
    combined_labels = np.concatenate([static_labels, movement_labels], axis=0)
    
    # Shuffle
    indices = np.random.permutation(len(combined_data))
    
    return combined_data[indices], combined_labels[indices]


def apply_electrode_dropout_augmentation(
    data: np.ndarray,
    drop_prob: float = 0.1,
    n_augmentations: int = 2
) -> np.ndarray:
    """
    Apply electrode dropout augmentation to training data.
    
    Creates augmented samples with random electrodes zeroed out,
    teaching robustness to bad contacts.
    
    Parameters:
    -----------
    data : np.ndarray
        Original data (n_samples, seq_len, n_channels)
    drop_prob : float
        Probability of dropping each electrode
    n_augmentations : int
        Number of augmented copies per original sample
        
    Returns:
    --------
    Augmented data (n_samples * (1 + n_augmentations), seq_len, n_channels)
    """
    n_samples, seq_len, n_channels = data.shape
    
    augmented_list = [data]  # Original data
    
    for _ in range(n_augmentations):
        augmented = data.copy()
        
        for i in range(n_samples):
            # Random electrode dropout mask
            mask = np.random.random(n_channels) > drop_prob
            augmented[i] = augmented[i] * mask
        
        augmented_list.append(augmented)
    
    return np.concatenate(augmented_list, axis=0)


class PretrainedModelManager:
    """
    Manages pretrained models for transfer learning.
    """
    
    def __init__(self, models_dir: str = "models/pretrained"):
        self.models_dir = Path(models_dir)
        self.models_dir.mkdir(parents=True, exist_ok=True)
    
    def save_pretrained(self, model: nn.Module, name: str, config: Dict):
        """Save pretrained model."""
        path = self.models_dir / f"{name}.pth"
        torch.save({
            'model_state_dict': model.state_dict(),
            'config': config
        }, path)
        print(f"Pretrained model saved: {path}")
    
    def load_pretrained(self, name: str) -> Tuple[Dict, Dict]:
        """Load pretrained model state dict and config."""
        path = self.models_dir / f"{name}.pth"
        if not path.exists():
            raise FileNotFoundError(f"Pretrained model not found: {path}")
        
        checkpoint = torch.load(path, map_location='cpu')
        return checkpoint['model_state_dict'], checkpoint['config']
    
    def list_pretrained(self) -> List[str]:
        """List available pretrained models."""
        return [p.stem for p in self.models_dir.glob("*.pth")]
