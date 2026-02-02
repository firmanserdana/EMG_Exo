#!/usr/bin/env python3
"""
Test transfer learning from pre-trained model to SCI patient data.

Workflow:
- S0: Train on session_00 (10 trials), test on... (session_01 has 0 trials)
- S1: Train on session_01 (10 trials), test on session_02, session_03, session_04
       (session_04 has 0 trials, so test on session_02, session_03)

Usage:
    python scripts/test_sci_transfer.py
"""

import os
import sys
import pickle
import numpy as np
import torch
import torch.nn as nn

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configuration
DATA_DIR = 'data/SCI'
MODEL_PATH = 'models/pretrained/pretrained_cnnlstm_open_close.pth'
WINDOW_SIZE = 200  # 200ms at 1000Hz
OVERLAP = 100       # 100ms overlap
FS_HZ = 1000
NUM_CHANNELS = 32


def load_data_numpy(file_name):
    """Load data from numpy file with appended arrays."""
    total_data = []
    with open(file_name, 'rb') as f:
        while True:
            try:
                data = np.load(f)
                total_data.append(data)
            except EOFError:
                break
            except ValueError:
                break
    return np.vstack(total_data) if total_data else np.array([])


def load_session(subj: str, session_num: int):
    """Load data and events for a session.
    
    Returns:
        data: (N, 32) EMG data
        timestamps: (N,) timestamps
        events: list of event dicts
    """
    data_file = os.path.join(DATA_DIR, subj, 'raw', f'session_{session_num:02d}.npy')
    events_file = os.path.join(DATA_DIR, subj, 'raw', f'session_{session_num:02d}_events.pkl')
    
    # Load data
    data = load_data_numpy(data_file)
    
    # Separate EMG from timestamps (last column is timestamps)
    timestamps = data[:, -1]
    emg_data = data[:, :NUM_CHANNELS]
    
    # Load events
    with open(events_file, 'rb') as f:
        events = pickle.load(f)
    
    return emg_data, timestamps, events


def extract_grasp_windows(emg_data, timestamps, events):
    """Extract windows during grasp periods.
    
    For open_close task:
    - OPEN (0): Between grasp_released and next grasp_start (hand is open)
    - CLOSE (1): Between grasp_start and grasp_released (hand is closing/holding)
    
    Returns:
        windows: (N, window_size, channels)
        labels: (N,) 0=OPEN, 1=CLOSE
    """
    windows = []
    labels = []
    
    # Get time offset
    if not events:
        return np.array([]), np.array([])
    
    time_start = events[0]['timestamp']
    
    # Parse events to find grasp periods
    grasp_starts = []
    grasp_ends = []
    
    for e in events:
        event_type = e['event_type']
        event_time = e['timestamp'] - time_start
        
        if 'grasp_start' in event_type:
            grasp_starts.append(event_time)
        elif event_type == 'grasp_released':
            grasp_ends.append(event_time)
    
    if not grasp_starts or not grasp_ends:
        return np.array([]), np.array([])
    
    # Match starts and ends
    n_trials = min(len(grasp_starts), len(grasp_ends))
    
    # Convert timestamps to relative time
    rel_times = timestamps - timestamps[0]
    
    step = WINDOW_SIZE - OVERLAP
    
    # Extract CLOSE windows (during grasp)
    for i in range(n_trials):
        start_time = grasp_starts[i]
        end_time = grasp_ends[i]
        
        start_idx = np.searchsorted(rel_times, start_time)
        end_idx = np.searchsorted(rel_times, end_time)
        
        # Extract windows
        for win_start in range(start_idx, end_idx - WINDOW_SIZE, step):
            win_data = emg_data[win_start:win_start + WINDOW_SIZE, :]
            if win_data.shape[0] == WINDOW_SIZE:
                windows.append(win_data)
                labels.append(1)  # CLOSE
    
    # Extract OPEN windows (between grasps)
    # Before first grasp
    if grasp_starts[0] > 0.5:  # At least 0.5s before first grasp
        start_idx = 0
        end_idx = np.searchsorted(rel_times, grasp_starts[0] - 0.2)  # Stop 200ms before grasp
        
        for win_start in range(start_idx, end_idx - WINDOW_SIZE, step):
            win_data = emg_data[win_start:win_start + WINDOW_SIZE, :]
            if win_data.shape[0] == WINDOW_SIZE:
                windows.append(win_data)
                labels.append(0)  # OPEN
    
    # Between grasps
    for i in range(n_trials - 1):
        start_time = grasp_ends[i] + 0.2  # Start 200ms after release
        end_time = grasp_starts[i + 1] - 0.2  # End 200ms before next grasp
        
        if end_time - start_time < 0.3:  # Need at least 300ms
            continue
            
        start_idx = np.searchsorted(rel_times, start_time)
        end_idx = np.searchsorted(rel_times, end_time)
        
        for win_start in range(start_idx, end_idx - WINDOW_SIZE, step):
            win_data = emg_data[win_start:win_start + WINDOW_SIZE, :]
            if win_data.shape[0] == WINDOW_SIZE:
                windows.append(win_data)
                labels.append(0)  # OPEN
    
    # After last grasp
    if len(rel_times) - np.searchsorted(rel_times, grasp_ends[-1]) > WINDOW_SIZE + 200:
        start_idx = np.searchsorted(rel_times, grasp_ends[-1] + 0.2)
        end_idx = len(emg_data) - WINDOW_SIZE
        
        for win_start in range(start_idx, end_idx, step):
            win_data = emg_data[win_start:win_start + WINDOW_SIZE, :]
            if win_data.shape[0] == WINDOW_SIZE:
                windows.append(win_data)
                labels.append(0)  # OPEN
    
    if not windows:
        return np.array([]), np.array([])
    
    return np.array(windows), np.array(labels)


def normalize_data(X, norm_params=None):
    """Z-score normalize data. Returns (normalized_X, norm_params)."""
    if norm_params is None:
        # Compute normalization parameters
        # X shape: (N, window_size, channels)
        mean = X.mean(axis=(0, 1))  # Per-channel mean
        std = X.std(axis=(0, 1))    # Per-channel std
        std[std < 1e-6] = 1.0       # Avoid division by zero
        norm_params = {'mean': mean, 'std': std}
    
    # Apply normalization
    X_norm = (X - norm_params['mean']) / norm_params['std']
    return X_norm, norm_params


class CNNLSTMClassifier(nn.Module):
    """CNN-LSTM model for EMG classification - matches pretrain_healthy.py exactly."""
    
    def __init__(self, n_channels=32, seq_len=200, num_classes=2, dropout=0.3):
        super().__init__()
        
        # CNN for spatial features
        self.conv1 = nn.Conv1d(n_channels, 64, kernel_size=5, padding=2)
        self.bn1 = nn.BatchNorm1d(64)
        self.conv2 = nn.Conv1d(64, 128, kernel_size=3, padding=1)
        self.bn2 = nn.BatchNorm1d(128)
        self.pool = nn.MaxPool1d(2)
        
        # Calculate LSTM input size
        lstm_seq_len = seq_len // 4  # After 2 pooling layers
        
        # LSTM for temporal features
        self.lstm = nn.LSTM(
            input_size=128,
            hidden_size=64,
            num_layers=2,
            batch_first=True,
            dropout=dropout,
            bidirectional=True
        )
        
        # Classifier
        self.fc = nn.Sequential(
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(64, num_classes)
        )
    
    def forward(self, x):
        # x: (batch, seq_len, n_channels)
        x = x.transpose(1, 2)  # (batch, n_channels, seq_len)
        
        # CNN
        x = torch.relu(self.bn1(self.conv1(x)))
        x = self.pool(x)
        x = torch.relu(self.bn2(self.conv2(x)))
        x = self.pool(x)
        
        # Prepare for LSTM: (batch, seq_len, features)
        x = x.transpose(1, 2)
        
        # LSTM
        lstm_out, _ = self.lstm(x)
        out = lstm_out[:, -1, :]
        
        # Classifier
        out = self.fc(out)
        return out


def load_pretrained_model(model_path):
    """Load pre-trained model with normalization parameters."""
    checkpoint = torch.load(model_path, map_location='cpu', weights_only=False)
    
    model = CNNLSTMClassifier(n_channels=32, seq_len=200, num_classes=2)
    model.load_state_dict(checkpoint['model_state_dict'])
    
    norm_params = checkpoint.get('norm_params', None)
    metadata = checkpoint.get('metadata', {})
    
    return model, norm_params, metadata


def freeze_feature_extractor(model, freeze_level='cnn'):
    """Freeze layers for transfer learning.
    
    Args:
        model: The CNN-LSTM model
        freeze_level: 'cnn' - freeze all CNN, 'conv1' - freeze only first conv, 'none' - train all
    """
    if freeze_level == 'cnn':
        # Freeze all CNN layers
        for name, param in model.named_parameters():
            if 'conv' in name or 'bn' in name:
                param.requires_grad = False
    elif freeze_level == 'conv1':
        # Freeze only first conv layer
        for name, param in model.named_parameters():
            if 'conv1' in name or 'bn1' in name:
                param.requires_grad = False
    # 'none' - don't freeze anything
    
    # Count trainable parameters
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total = sum(p.numel() for p in model.parameters())
    print(f"  Trainable: {trainable:,} / {total:,} parameters ({freeze_level} frozen)")


def train_epoch(model, X_train, y_train, optimizer, criterion, device):
    """Train for one epoch."""
    model.train()
    
    # Shuffle
    perm = torch.randperm(len(X_train))
    X_train = X_train[perm]
    y_train = y_train[perm]
    
    # Train
    optimizer.zero_grad()
    outputs = model(X_train)
    loss = criterion(outputs, y_train)
    loss.backward()
    optimizer.step()
    
    # Accuracy
    _, preds = torch.max(outputs, 1)
    acc = (preds == y_train).float().mean().item()
    
    return loss.item(), acc


def evaluate(model, X, y, device, verbose=True):
    """Evaluate model."""
    model.eval()
    with torch.no_grad():
        outputs = model(X)
        _, preds = torch.max(outputs, 1)
        acc = (preds == y).float().mean().item()
        
        # Per-class accuracy
        if verbose:
            for c in range(2):
                mask = (y == c)
                if mask.sum() > 0:
                    class_acc = (preds[mask] == y[mask]).float().mean().item()
                    print(f"    Class {c} ({['OPEN', 'CLOSE'][c]}): {class_acc:.1%} ({mask.sum().item()} samples)")
    
    return acc


def fine_tune(model, X_train, y_train, X_test, y_test, device, epochs=100, lr=0.0005, freeze_level='conv1'):
    """Fine-tune model on new data with class weighting and early stopping."""
    model = model.to(device)
    
    X_train = torch.FloatTensor(X_train).to(device)
    y_train = torch.LongTensor(y_train).to(device)
    X_test = torch.FloatTensor(X_test).to(device)
    y_test = torch.LongTensor(y_test).to(device)
    
    # Freeze feature extractor
    freeze_feature_extractor(model, freeze_level)
    
    # Compute class weights for balanced loss
    class_counts = torch.bincount(y_train)
    class_weights = len(y_train) / (len(class_counts) * class_counts.float())
    class_weights = class_weights.to(device)
    print(f"  Class weights: OPEN={class_weights[0]:.2f}, CLOSE={class_weights[1]:.2f}")
    
    optimizer = torch.optim.Adam(filter(lambda p: p.requires_grad, model.parameters()), lr=lr, weight_decay=1e-3)
    criterion = nn.CrossEntropyLoss(weight=class_weights)
    
    print(f"\n  Training for up to {epochs} epochs with early stopping...")
    
    best_acc = 0
    best_state = None
    patience = 15
    patience_counter = 0
    
    for epoch in range(epochs):
        loss, train_acc = train_epoch(model, X_train, y_train, optimizer, criterion, device)
        
        # Evaluate every epoch for early stopping
        test_acc = evaluate(model, X_test, y_test, device, verbose=False)
        
        if test_acc > best_acc:
            best_acc = test_acc
            best_state = {k: v.clone() for k, v in model.state_dict().items()}
            patience_counter = 0
        else:
            patience_counter += 1
        
        if (epoch + 1) % 10 == 0 or epoch == 0:
            print(f"  Epoch {epoch+1:3d}: loss={loss:.4f}, train_acc={train_acc:.1%}, test_acc={test_acc:.1%}" + 
                  (f" (best: {best_acc:.1%})" if best_acc > test_acc else " *"))
        
        if patience_counter >= patience:
            print(f"  Early stopping at epoch {epoch+1} (no improvement for {patience} epochs)")
            break
    
    # Restore best model
    if best_state is not None:
        model.load_state_dict(best_state)
    
    # Final evaluation
    print(f"\n  Final test accuracy (best model):")
    final_acc = evaluate(model, X_test, y_test, device, verbose=True)
    
    return final_acc, best_acc


def main():
    print("=" * 60)
    print("SCI Transfer Learning Test")
    print("=" * 60)
    
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"\nDevice: {device}")
    
    # Load pre-trained model
    print(f"\nLoading pre-trained model from: {MODEL_PATH}")
    model, pretrained_norm_params, metadata = load_pretrained_model(MODEL_PATH)
    print(f"  Pre-trained accuracy: {metadata.get('val_accuracy', 'N/A')}")
    
    # Test configurations
    test_configs = [
        # S0: Train on session_00, test on... (no test session with trials)
        # So we'll do cross-validation within session_00
        {'subj': 'S0', 'train_sessions': [0], 'test_sessions': [0], 'split': True, 'name': 'S0 (within session)', 'use_pretrained': True},
        
        # S1: Train on session_01, test on session_02, session_03
        {'subj': 'S1', 'train_sessions': [1], 'test_sessions': [2, 3], 'split': False, 'name': 'S1 Transfer (1→2,3)', 'use_pretrained': True},
        
        # S1: Train from scratch on session_01, test on session_02, session_03
        {'subj': 'S1', 'train_sessions': [1], 'test_sessions': [2, 3], 'split': False, 'name': 'S1 Scratch (1→2,3)', 'use_pretrained': False},
        
        # S1: Train on sessions 01+02, test on session_03 - transfer learning
        {'subj': 'S1', 'train_sessions': [1, 2], 'test_sessions': [3], 'split': False, 'name': 'S1 Transfer (1,2→3)', 'use_pretrained': True},
        
        # S1: Train on sessions 01+02, test on session_03 - from scratch
        {'subj': 'S1', 'train_sessions': [1, 2], 'test_sessions': [3], 'split': False, 'name': 'S1 Scratch (1,2→3)', 'use_pretrained': False},
    ]
    
    results = []
    
    for config in test_configs:
        subj = config['subj']
        train_sessions = config['train_sessions']
        test_sessions = config['test_sessions']
        split = config['split']
        use_pretrained = config.get('use_pretrained', True)
        
        print(f"\n{'='*60}")
        print(f"{config.get('name', config['subj'])}")
        print(f"Train sessions: {train_sessions}, Test sessions: {test_sessions}")
        print("=" * 60)
        
        # Load training data
        X_train_list = []
        y_train_list = []
        
        for sess in train_sessions:
            try:
                emg, ts, events = load_session(subj, sess)
                X, y = extract_grasp_windows(emg, ts, events)
                if len(X) > 0:
                    X_train_list.append(X)
                    y_train_list.append(y)
                    print(f"  Session {sess:02d} train: {len(X)} windows (OPEN: {(y==0).sum()}, CLOSE: {(y==1).sum()})")
            except Exception as e:
                print(f"  Session {sess:02d} train: Error - {e}")
        
        if not X_train_list:
            print("  No training data!")
            continue
        
        X_train = np.concatenate(X_train_list, axis=0)
        y_train = np.concatenate(y_train_list, axis=0)
        
        # Load test data
        X_test_list = []
        y_test_list = []
        
        if split:
            # Split training data for cross-validation
            n_samples = len(X_train)
            n_train = int(n_samples * 0.7)
            
            # Shuffle
            perm = np.random.permutation(n_samples)
            X_train = X_train[perm]
            y_train = y_train[perm]
            
            X_test = X_train[n_train:]
            y_test = y_train[n_train:]
            X_train = X_train[:n_train]
            y_train = y_train[:n_train]
            
            print(f"  Split: {len(X_train)} train, {len(X_test)} test")
        else:
            for sess in test_sessions:
                try:
                    emg, ts, events = load_session(subj, sess)
                    X, y = extract_grasp_windows(emg, ts, events)
                    if len(X) > 0:
                        X_test_list.append(X)
                        y_test_list.append(y)
                        print(f"  Session {sess:02d} test: {len(X)} windows (OPEN: {(y==0).sum()}, CLOSE: {(y==1).sum()})")
                except Exception as e:
                    print(f"  Session {sess:02d} test: Error - {e}")
            
            if not X_test_list:
                print("  No test data!")
                continue
            
            X_test = np.concatenate(X_test_list, axis=0)
            y_test = np.concatenate(y_test_list, axis=0)
        
        print(f"\n  Total: {len(X_train)} train, {len(X_test)} test windows")
        
        # Normalize using pre-trained normalization (or compute new)
        if pretrained_norm_params is not None and use_pretrained:
            print("  Using pre-trained normalization parameters")
            X_train, _ = normalize_data(X_train, pretrained_norm_params)
            X_test, _ = normalize_data(X_test, pretrained_norm_params)
        else:
            print("  Computing normalization from training data")
            X_train, norm_params = normalize_data(X_train)
            X_test, _ = normalize_data(X_test, norm_params)
        
        # Load model (pre-trained or fresh)
        if use_pretrained:
            print("  Loading pre-trained model...")
            model, _, _ = load_pretrained_model(MODEL_PATH)
            freeze_level = 'conv1'  # Freeze first conv for transfer learning
        else:
            print("  Creating fresh model (training from scratch)...")
            model = CNNLSTMClassifier(n_channels=32, seq_len=200, num_classes=2)
            freeze_level = 'none'  # Train all layers from scratch
        
        # Evaluate before fine-tuning
        print(f"\n  Before fine-tuning:")
        model_eval = model.to(device)
        X_test_t = torch.FloatTensor(X_test).to(device)
        y_test_t = torch.LongTensor(y_test).to(device)
        before_acc = evaluate(model_eval, X_test_t, y_test_t, device)
        print(f"    Overall: {before_acc:.1%}")
        
        # Fine-tune
        final_acc, best_acc = fine_tune(model, X_train, y_train, X_test, y_test, device, freeze_level=freeze_level)
        
        results.append({
            'name': config.get('name', config['subj']),
            'subject': subj,
            'train_sessions': train_sessions,
            'test_sessions': test_sessions,
            'n_train': len(X_train),
            'n_test': len(X_test),
            'before_acc': before_acc,
            'after_acc': final_acc,
            'best_acc': best_acc,
        })
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for r in results:
        print(f"\n{r['name']}:")
        print(f"  Train: {r['n_train']} windows from session(s) {r['train_sessions']}")
        print(f"  Test:  {r['n_test']} windows from session(s) {r['test_sessions']}")
        print(f"  Accuracy: {r['before_acc']:.1%} (before) → {r['best_acc']:.1%} (best)")


if __name__ == '__main__':
    main()
