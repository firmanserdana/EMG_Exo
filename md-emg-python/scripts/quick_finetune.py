"""
Quick Fine-tuning for Small Datasets (e.g., 10 trials).

Optimized for speed when you have very few training samples.

Usage:
    python scripts/quick_finetune.py \
        --pretrained models/pretrained/pretrained_cnnlstm_open_close.pth \
        --data_file data/SCI/S1/raw/session_01_emg.pkl \
        --events_file data/SCI/S1/raw/session_01_events.pkl
"""

import argparse
import torch
import torch.nn as nn
import numpy as np
from pathlib import Path
import time
import sys
import pickle

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.pretrain_healthy import (
    build_lstm_model, build_cnn_lstm_model,
    apply_normalization, NUM_CHANNELS
)


def load_pretrained_fast(pretrained_path: str, freeze_features: bool = True):
    """Load pre-trained model optimized for fast fine-tuning.
    
    Args:
        pretrained_path: Path to .pth file
        freeze_features: If True, only train classifier (much faster)
    
    Returns:
        model, metadata
    """
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    checkpoint = torch.load(pretrained_path, map_location=device)
    
    model_type = checkpoint['model_type']
    num_classes = checkpoint['num_classes']
    n_channels = checkpoint.get('n_channels', NUM_CHANNELS)
    window_ms = checkpoint.get('window_ms', 200)
    seq_len = int(window_ms)  # Assuming 1000 Hz
    
    # Build model
    if model_type == 'LSTM':
        model = build_lstm_model(input_size=n_channels, num_classes=num_classes)
    else:
        model = build_cnn_lstm_model(n_channels=n_channels, seq_len=seq_len, num_classes=num_classes)
    
    model.load_state_dict(checkpoint['model_state_dict'])
    
    # Freeze feature layers for speed
    if freeze_features:
        for name, param in model.named_parameters():
            if 'fc' not in name:  # Only keep classifier trainable
                param.requires_grad = False
    
    model = model.to(device)
    
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total = sum(p.numel() for p in model.parameters())
    
    metadata = {
        'model_type': model_type,
        'num_classes': num_classes,
        'norm_params': checkpoint.get('norm_params'),
        'window_ms': window_ms,
        'device': device
    }
    
    print(f"✅ Loaded {model_type} ({trainable:,}/{total:,} trainable params)")
    
    return model, metadata


def fast_train(model, X_train, y_train, X_val, y_val, 
               epochs: int = 20, lr: float = 0.001, device: str = 'cpu'):
    """Ultra-fast training loop for small datasets.
    
    Optimizations:
    - No DataLoader overhead (data fits in memory)
    - Minimal validation (every 5 epochs)
    - Aggressive early stopping (patience=5)
    """
    X_train = torch.tensor(X_train, dtype=torch.float32).to(device)
    y_train = torch.tensor(y_train, dtype=torch.long).to(device)
    X_val = torch.tensor(X_val, dtype=torch.float32).to(device)
    y_val = torch.tensor(y_val, dtype=torch.long).to(device)
    
    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.Adam(
        filter(lambda p: p.requires_grad, model.parameters()),
        lr=lr
    )
    
    best_val_acc = 0
    best_state = None
    patience_counter = 0
    patience = 5
    
    start_time = time.time()
    
    for epoch in range(epochs):
        # Training - single batch (data is small)
        model.train()
        optimizer.zero_grad()
        outputs = model(X_train)
        loss = criterion(outputs, y_train)
        loss.backward()
        optimizer.step()
        
        train_acc = (outputs.argmax(1) == y_train).float().mean().item()
        
        # Validation every 5 epochs or last epoch
        if (epoch + 1) % 5 == 0 or epoch == epochs - 1:
            model.eval()
            with torch.no_grad():
                val_outputs = model(X_val)
                val_acc = (val_outputs.argmax(1) == y_val).float().mean().item()
            
            print(f"  Epoch {epoch+1:3d} | Train: {train_acc:.2%} | Val: {val_acc:.2%}")
            
            if val_acc > best_val_acc:
                best_val_acc = val_acc
                best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}
                patience_counter = 0
            else:
                patience_counter += 1
                if patience_counter >= patience:
                    print(f"  Early stop at epoch {epoch+1}")
                    break
    
    elapsed = time.time() - start_time
    
    if best_state:
        model.load_state_dict(best_state)
    
    return model, best_val_acc, elapsed


def prepare_windows(emg_data: np.ndarray, events: dict, 
                    window_ms: int = 200, overlap_ms: int = 100, fs: int = 1000):
    """Prepare training windows from EMG data and events.
    
    Args:
        emg_data: Raw EMG (n_samples, n_channels)
        events: List of event dicts or dict with trial events
        window_ms: Window size in ms
        overlap_ms: Overlap in ms
        fs: Sampling rate
    
    Returns:
        X: Windows (n_windows, window_samples, n_channels)
        y: Labels (n_windows,)
    """
    window_samples = int(window_ms * fs / 1000)
    step_samples = int((window_ms - overlap_ms) * fs / 1000)
    
    windows = []
    labels = []
    
    # Parse events - handle both list and dict formats
    if isinstance(events, list):
        # Convert event list to trials format
        # Events are like: grasp_start_0, grasp_hold_start, grasp_hold_end, grasp_start_1, etc.
        trials = []
        current_trial = {}
        
        # Find session_start timestamp to make times relative
        session_start_ts = None
        for event in events:
            if event.get('event_type') == 'session_start':
                session_start_ts = event.get('timestamp', 0)
                break
        
        if session_start_ts is None and events:
            # Use first event timestamp as reference
            session_start_ts = events[0].get('timestamp', 0)
        
        for event in events:
            event_type = event.get('event_type', '')
            timestamp = event.get('timestamp', 0) - (session_start_ts or 0)  # Make relative
            
            # Detect grasp label from grasp_start_N events
            if event_type.startswith('grasp_start_'):
                label = int(event_type.split('_')[-1])
                current_trial = {'label': label}
            elif event_type == 'grasp_hold_start':
                current_trial['grasp_hold_start'] = timestamp
            elif event_type == 'grasp_hold_end':
                current_trial['grasp_hold_end'] = timestamp
                if 'grasp_hold_start' in current_trial and 'label' in current_trial:
                    trials.append(current_trial)
                current_trial = {}
        
        print(f"   Parsed {len(trials)} trials from events")
        for i, t in enumerate(trials[:3]):
            print(f"      Trial {i}: label={t['label']}, {t['grasp_hold_start']:.2f}s - {t['grasp_hold_end']:.2f}s")
    else:
        trials = events.get('trials', [])
    
    n_samples = emg_data.shape[0]
    print(f"   EMG data: {n_samples} samples ({n_samples/fs:.2f}s)")
    
    for trial_idx, trial in enumerate(trials):
        start_time = trial.get('grasp_hold_start', trial.get('start', 0))
        end_time = trial.get('grasp_hold_end', trial.get('end', 0))
        label = trial.get('label', 0)  # 0=OPEN, 1=CLOSE
        
        start_idx = int(start_time * fs)
        end_idx = int(end_time * fs)
        
        # Skip trials that are beyond the EMG data
        if end_idx > n_samples:
            print(f"   ⚠️  Trial {trial_idx} ({start_time:.2f}s-{end_time:.2f}s) beyond data, skipping")
            continue
        
        trial_windows = 0
        # Extract windows from this trial
        for i in range(start_idx, end_idx - window_samples + 1, step_samples):
            if i + window_samples <= n_samples:
                window = emg_data[i:i + window_samples, :NUM_CHANNELS]
                if window.shape[0] == window_samples:
                    windows.append(window)
                    labels.append(label)
                    trial_windows += 1
        
        if trial_windows > 0:
            print(f"   Trial {trial_idx}: label={label}, {trial_windows} windows extracted")
    
    print(f"   Total: {len(windows)} windows")
    return np.array(windows), np.array(labels)


def main():
    parser = argparse.ArgumentParser(description='Quick fine-tuning for small datasets')
    parser.add_argument('--pretrained', type=str, 
                        default='models/pretrained/pretrained_cnnlstm_open_close.pth',
                        help='Path to pre-trained model')
    parser.add_argument('--data_file', type=str, help='Path to EMG data file (.pkl or .npy)')
    parser.add_argument('--events_file', type=str, help='Path to events file (.pkl)')
    parser.add_argument('--epochs', type=int, default=30, help='Max epochs')
    parser.add_argument('--lr', type=float, default=0.001, help='Learning rate')
    parser.add_argument('--freeze', action='store_true', default=True,
                        help='Freeze feature extractor (default: True for speed)')
    parser.add_argument('--no_freeze', dest='freeze', action='store_false',
                        help='Train all layers')
    parser.add_argument('--output', type=str, help='Output model path')
    
    args = parser.parse_args()
    
    print("\n" + "="*50)
    print("⚡ Quick Fine-tuning (optimized for small data)")
    print("="*50)
    
    # Load pre-trained model
    print("\n📥 Loading pre-trained model...")
    model, metadata = load_pretrained_fast(args.pretrained, freeze_features=args.freeze)
    device = metadata['device']
    
    # Demo with synthetic data if no data file provided
    if not args.data_file:
        print("\n📝 No data file provided. Running demo with synthetic data...")
        
        # Simulate 10 trials (5 open, 5 close)
        n_windows_per_class = 140  # ~5 trials * 28 windows
        window_samples = 200
        
        X_open = np.random.randn(n_windows_per_class, window_samples, NUM_CHANNELS) * 0.5
        X_close = np.random.randn(n_windows_per_class, window_samples, NUM_CHANNELS) * 1.5 + 0.5
        
        X = np.concatenate([X_open, X_close])
        y = np.array([0] * n_windows_per_class + [1] * n_windows_per_class)
        
        # Shuffle
        idx = np.random.permutation(len(X))
        X, y = X[idx], y[idx]
        
    else:
        # Load actual data
        print(f"\n📂 Loading data from {args.data_file}...")
        
        if args.data_file.endswith('.pkl'):
            with open(args.data_file, 'rb') as f:
                emg_data = pickle.load(f)
        else:
            # Load .npy file with multiple concatenated arrays (streaming format)
            arrays = []
            with open(args.data_file, 'rb') as f:
                while True:
                    try:
                        arrays.append(np.load(f, allow_pickle=False))
                    except (ValueError, EOFError):
                        break
            if not arrays:
                raise ValueError(f"No data found in {args.data_file}")
            emg_data = np.concatenate(arrays, axis=0)
            print(f"   Loaded {len(arrays)} chunks, total shape: {emg_data.shape}")
        
        with open(args.events_file, 'rb') as f:
            events = pickle.load(f)
        
        X, y = prepare_windows(emg_data, events, window_ms=metadata['window_ms'])
        print(f"   Windows: {len(X)} ({(y==0).sum()} open, {(y==1).sum()} close)")
    
    # Apply normalization from pre-trained model
    if metadata.get('norm_params'):
        print("\n📈 Applying normalization...")
        X = apply_normalization(X, metadata['norm_params'])
    
    # Split data (80/20)
    split_idx = int(len(X) * 0.8)
    idx = np.random.permutation(len(X))
    X, y = X[idx], y[idx]
    X_train, X_val = X[:split_idx], X[split_idx:]
    y_train, y_val = y[:split_idx], y[split_idx:]
    
    print(f"   Train: {len(X_train)}, Val: {len(X_val)}")
    
    # Fast training
    print(f"\n🚀 Training (max {args.epochs} epochs, lr={args.lr})...")
    model, best_acc, elapsed = fast_train(
        model, X_train, y_train, X_val, y_val,
        epochs=args.epochs, lr=args.lr, device=device
    )
    
    # Save model
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = Path('models/finetuned_model.pth')
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    torch.save({
        'model_state_dict': model.state_dict(),
        'model_type': metadata['model_type'],
        'num_classes': metadata['num_classes'],
        'norm_params': metadata['norm_params'],
        'window_ms': metadata['window_ms'],
        'best_val_acc': best_acc
    }, output_path)
    
    print(f"\n✅ Model saved to: {output_path}")
    
    # Summary
    print("\n" + "="*50)
    print("📊 Summary")
    print("="*50)
    print(f"   Training time: {elapsed:.2f} seconds")
    print(f"   Best accuracy: {best_acc:.2%}")
    print(f"   Windows/sec: {len(X_train) * args.epochs / elapsed:.0f}")
    print("="*50 + "\n")


if __name__ == '__main__':
    main()
