"""
Transfer Learning Utilities for EMG Classification.

Load a pre-trained model from healthy subjects and fine-tune on SCI patient data.

Usage:
    # Fine-tune all layers with lower learning rate
    python scripts/transfer_learning.py \
        --pretrained models/pretrained/pretrained_cnnlstm_open_close.pth \
        --subj 1 \
        --subj_type SCI \
        --epochs 50

    # Freeze feature extractor, only train classifier
    python scripts/transfer_learning.py \
        --pretrained models/pretrained/pretrained_cnnlstm_open_close.pth \
        --subj 1 \
        --subj_type SCI \
        --freeze_features \
        --epochs 30
"""

import argparse
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset
import numpy as np
from pathlib import Path
import yaml
import sys
import os
import pickle
from sklearn.preprocessing import LabelEncoder

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.pretrain_healthy import (
    build_lstm_model, build_cnn_lstm_model,
    normalize_emg, apply_normalization, EMGDataset,
    NUM_CHANNELS
)


def _build_model_from_checkpoint(checkpoint, device):
    """Build model using architecture stored in checkpoint's model_hparams (pipeline models)
    or fall back to fixed default architecture (pretrain_healthy.py models)."""
    model_type = checkpoint['model_type']
    num_classes = checkpoint['num_classes']
    n_channels = checkpoint.get('n_channels', NUM_CHANNELS)
    window_ms = checkpoint.get('window_ms', 200)
    params = checkpoint.get('model_hparams', {})

    if model_type == 'LSTM':
        if params.get('hidden_size') or params.get('num_layers'):
            # Pipeline HPO model - import TunableLSTM
            try:
                from scripts.train_transfer_pipeline_cli import TunableLSTM
                model = TunableLSTM(
                    input_size=n_channels,
                    hidden_size=int(params['hidden_size']),
                    num_layers=int(params['num_layers']),
                    num_classes=num_classes,
                    dropout=float(params.get('dropout', 0.3)),
                )
            except (ImportError, KeyError):
                model = build_lstm_model(input_size=n_channels, num_classes=num_classes)
        else:
            model = build_lstm_model(input_size=n_channels, num_classes=num_classes)
    else:  # CNNLSTM
        seq_len = int(window_ms * 1000 / 1000)
        if params.get('conv1_channels') or params.get('lstm_hidden'):
            try:
                from scripts.train_transfer_pipeline_cli import TunableCNNLSTM
                model = TunableCNNLSTM(
                    n_channels=n_channels,
                    seq_len=seq_len,
                    num_classes=num_classes,
                    conv1_channels=int(params.get('conv1_channels', 64)),
                    conv2_channels=int(params.get('conv2_channels', 128)),
                    lstm_hidden=int(params.get('lstm_hidden', 64)),
                    lstm_layers=int(params.get('lstm_layers', 2)),
                    dropout=float(params.get('dropout', 0.3)),
                )
            except (ImportError, KeyError):
                model = build_cnn_lstm_model(n_channels=n_channels, seq_len=seq_len, num_classes=num_classes)
        else:
            model = build_cnn_lstm_model(n_channels=n_channels, seq_len=seq_len, num_classes=num_classes)

    return model


def load_pretrained_model(pretrained_path: str, device: str = 'cuda'):
    """Load a pre-trained model with all metadata.
    
    Args:
        pretrained_path: Path to .pth file
        device: 'cuda' or 'cpu'
    
    Returns:
        model: PyTorch model with loaded weights
        metadata: Dict with training info and normalization params
    """
    checkpoint = torch.load(pretrained_path, map_location=device)
    
    model_type = checkpoint['model_type']
    num_classes = checkpoint['num_classes']
    n_channels = checkpoint.get('n_channels', NUM_CHANNELS)
    window_ms = checkpoint.get('window_ms', 200)
    
    # Build model architecture (handles both fixed-arch and HPO-arch checkpoints)
    model = _build_model_from_checkpoint(checkpoint, device)

    # Load weights
    model.load_state_dict(checkpoint['model_state_dict'])
    model = model.to(device)
    
    metadata = {
        'model_type': model_type,
        'task': checkpoint.get('task'),
        'num_classes': num_classes,
        'n_channels': n_channels,
        'window_ms': window_ms,
        'norm_params': checkpoint.get('norm_params'),
        'subjects': checkpoint.get('subjects'),
        'conditions': checkpoint.get('conditions'),
        'best_val_acc': checkpoint.get('best_val_acc')
    }
    
    print(f"✅ Loaded pre-trained {model_type} model")
    print(f"   Task: {metadata['task']}, Classes: {num_classes}")
    print(f"   Pre-trained accuracy: {metadata['best_val_acc']:.2%}")
    
    return model, metadata


def freeze_feature_extractor(model, model_type: str):
    """Freeze feature extraction layers, only train classifier.
    
    For CNN-LSTM: Freeze conv layers and LSTM, train only FC layers
    For LSTM: Freeze LSTM, train only FC layers
    """
    if model_type == 'CNNLSTM':
        # Freeze CNN and LSTM layers
        for name, param in model.named_parameters():
            if 'fc' not in name:  # Keep FC (classifier) trainable
                param.requires_grad = False
                
    else:  # LSTM
        # Freeze LSTM layers
        for name, param in model.named_parameters():
            if 'lstm' in name:
                param.requires_grad = False
    
    # Count trainable parameters
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total = sum(p.numel() for p in model.parameters())
    print(f"   Frozen layers: {total - trainable:,} / {total:,} parameters")
    print(f"   Trainable: {trainable:,} parameters")
    
    return model


def fine_tune(
    model: nn.Module,
    train_loader: DataLoader,
    val_loader: DataLoader,
    epochs: int = 50,
    lr: float = 0.0001,  # Lower learning rate for fine-tuning
    device: str = 'cuda'
):
    """Fine-tune the model on new data.
    
    Args:
        model: Pre-trained model
        train_loader: Training data loader
        val_loader: Validation data loader
        epochs: Number of fine-tuning epochs
        lr: Learning rate (should be lower than pre-training)
        device: 'cuda' or 'cpu'
    
    Returns:
        model: Fine-tuned model
        history: Training history
    """
    device = torch.device(device if torch.cuda.is_available() else 'cpu')
    model = model.to(device)
    
    criterion = nn.CrossEntropyLoss()
    
    # Only optimize trainable parameters
    optimizer = torch.optim.Adam(
        filter(lambda p: p.requires_grad, model.parameters()),
        lr=lr,
        weight_decay=1e-4
    )
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode='min', factor=0.5, patience=5
    )
    
    history = {'train_loss': [], 'val_loss': [], 'train_acc': [], 'val_acc': []}
    best_val_loss = float('inf')
    best_model_state = None
    patience_counter = 0
    patience = 15
    
    for epoch in range(epochs):
        # Training
        model.train()
        train_loss = 0
        train_correct = 0
        train_total = 0
        
        for X_batch, y_batch in train_loader:
            X_batch = X_batch.to(device).float()
            y_batch = y_batch.to(device).long()
            
            optimizer.zero_grad()
            outputs = model(X_batch)
            loss = criterion(outputs, y_batch)
            loss.backward()
            optimizer.step()
            
            train_loss += loss.item()
            _, predicted = outputs.max(1)
            train_total += y_batch.size(0)
            train_correct += predicted.eq(y_batch).sum().item()
        
        train_loss /= len(train_loader)
        train_acc = train_correct / train_total
        
        # Validation
        model.eval()
        val_loss = 0
        val_correct = 0
        val_total = 0
        
        with torch.no_grad():
            for X_batch, y_batch in val_loader:
                X_batch = X_batch.to(device).float()
                y_batch = y_batch.to(device).long()
                
                outputs = model(X_batch)
                loss = criterion(outputs, y_batch)
                
                val_loss += loss.item()
                _, predicted = outputs.max(1)
                val_total += y_batch.size(0)
                val_correct += predicted.eq(y_batch).sum().item()
        
        val_loss /= len(val_loader)
        val_acc = val_correct / val_total
        
        scheduler.step(val_loss)
        
        history['train_loss'].append(train_loss)
        history['val_loss'].append(val_loss)
        history['train_acc'].append(train_acc)
        history['val_acc'].append(val_acc)
        
        if (epoch + 1) % 5 == 0:
            print(f"  Epoch {epoch+1}/{epochs} - "
                  f"Train: {train_acc:.4f}, Val: {val_acc:.4f}")
        
        # Early stopping
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            best_model_state = model.state_dict().copy()
            patience_counter = 0
        else:
            patience_counter += 1
            if patience_counter >= patience:
                print(f"  Early stopping at epoch {epoch+1}")
                break
    
    if best_model_state is not None:
        model.load_state_dict(best_model_state)
    
    return model, history


def load_sci_data(subj: int, subj_type: str = 'SCI', task: str = 'open_close'):
    """Load SCI patient data for fine-tuning.
    
    This is a placeholder - adapt to your actual data loading pipeline.
    """
    script_dir = Path(__file__).parent
    data_dir = script_dir.parent / 'data' / subj_type / f'S{subj}'
    
    # Try to load from standard locations
    raw_dir = data_dir / 'raw'
    
    if not raw_dir.exists():
        print(f"⚠️  Data directory not found: {raw_dir}")
        print("   Please ensure data is available or modify load_sci_data()")
        return None, None
    
    # Look for .pkl or .npy files
    data_files = list(raw_dir.glob('*.pkl')) + list(raw_dir.glob('*.npy'))
    
    if not data_files:
        print(f"⚠️  No data files found in {raw_dir}")
        return None, None
    
    print(f"📂 Found {len(data_files)} data files in {raw_dir}")
    
    # This needs to be adapted based on your actual data format
    # For now, return None to indicate data needs to be loaded manually
    return None, None


def main():
    parser = argparse.ArgumentParser(description='Fine-tune pre-trained EMG model')
    parser.add_argument('--pretrained', type=str, required=True,
                        help='Path to pre-trained model .pth file')
    parser.add_argument('--subj', type=int, required=True,
                        help='Subject number')
    parser.add_argument('--subj_type', type=str, default='SCI',
                        choices=['SCI', 'healthy'],
                        help='Subject type')
    parser.add_argument('--freeze_features', action='store_true',
                        help='Freeze feature extractor, only train classifier')
    parser.add_argument('--epochs', type=int, default=50,
                        help='Number of fine-tuning epochs')
    parser.add_argument('--lr', type=float, default=0.0001,
                        help='Learning rate (lower than pre-training)')
    parser.add_argument('--batch_size', type=int, default=32,
                        help='Batch size')
    parser.add_argument('--output_dir', type=str, default='models-subjects',
                        help='Output directory for fine-tuned model')
    parser.add_argument('--acquisition_type', type=str, default='open_loop',
                        choices=['open_loop', 'closed_loop', 'both'],
                        help='Acquisition type used for deployment naming (default: open_loop)')
    parser.add_argument('--task', type=str, default=None,
                        choices=['open_close', 'grasp_patterns', 'single_fingers', None],
                        help='Override task name if pretrained metadata has no task')
    
    args = parser.parse_args()
    
    print("\n" + "="*60)
    print("🔄 Transfer Learning: Fine-tuning Pre-trained Model")
    print("="*60)
    
    # Load pre-trained model
    print("\n📥 Loading pre-trained model...")
    model, metadata = load_pretrained_model(args.pretrained)
    
    # Optionally freeze feature extractor
    if args.freeze_features:
        print("\n❄️  Freezing feature extractor layers...")
        model = freeze_feature_extractor(model, metadata['model_type'])
    
    # Load SCI patient data
    print(f"\n📂 Loading {args.subj_type} subject {args.subj} data...")
    X, y = load_sci_data(args.subj, args.subj_type, metadata['task'])
    
    if X is None:
        print("\n" + "="*60)
        print("📝 Manual Data Loading Required")
        print("="*60)
        print("""
To fine-tune the model, you need to:

1. Record data using Unity VR open-loop mode:
   python emg_control_64.py --subj {subj} --subj_type {subj_type} --task open_close --decoding_active 0

2. Load and prepare your data:
   
   from scripts.pretrain_healthy import apply_normalization, EMGDataset
   from scripts.transfer_learning import load_pretrained_model, fine_tune
   
   # Load pre-trained model
   model, metadata = load_pretrained_model('{pretrained}')
   
   # Load your data (X: n_windows x n_samples x n_channels, y: labels)
   X = ...  # Your EMG windows
   y = ...  # Your labels (0=OPEN, 1=CLOSE)
   
   # Apply same normalization as pre-training
   X_norm = apply_normalization(X, metadata['norm_params'])
   
   # Split and create data loaders
   from torch.utils.data import DataLoader
   train_dataset = EMGDataset(X_train, y_train, augment=True)
   val_dataset = EMGDataset(X_val, y_val, augment=False)
   train_loader = DataLoader(train_dataset, batch_size=32, shuffle=True)
   val_loader = DataLoader(val_dataset, batch_size=32)
   
   # Fine-tune
   model, history = fine_tune(model, train_loader, val_loader, 
                              epochs=50, lr=0.0001)
   
   # Save fine-tuned model
   torch.save({{'model_state_dict': model.state_dict(), ...}}, 'model.pth')
        """.format(subj=args.subj, subj_type=args.subj_type, pretrained=args.pretrained))
        return
    
    # Apply normalization from pre-trained model
    if metadata.get('norm_params'):
        print("\n📈 Applying pre-trained normalization...")
        X = apply_normalization(X, metadata['norm_params'])
    
    # Split data
    indices = np.random.permutation(len(X))
    X, y = X[indices], y[indices]
    split_idx = int(len(X) * 0.8)
    X_train, X_val = X[:split_idx], X[split_idx:]
    y_train, y_val = y[:split_idx], y[split_idx:]
    
    # Create data loaders
    train_dataset = EMGDataset(X_train, y_train, augment=True)
    val_dataset = EMGDataset(X_val, y_val, augment=False)
    train_loader = DataLoader(train_dataset, batch_size=args.batch_size, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=args.batch_size)
    
    # Fine-tune
    print(f"\n🚀 Fine-tuning for {args.epochs} epochs (lr={args.lr})...")
    model, history = fine_tune(
        model, train_loader, val_loader,
        epochs=args.epochs,
        lr=args.lr
    )
    
    # Save fine-tuned model
    task_name = args.task if args.task is not None else metadata.get('task')
    if task_name is None:
        raise ValueError('Task is missing in pretrained metadata. Pass --task to set it explicitly.')

    output_dir = Path(args.output_dir) / args.subj_type / f'S{args.subj}' / task_name
    output_dir.mkdir(parents=True, exist_ok=True)

    # model_train-compatible naming used by active decoding
    model_name = f"{metadata['model_type']}_{args.acquisition_type}.pth"
    model_path = output_dir / model_name
    
    save_dict = {
        'model_state_dict': model.state_dict(),
        'model_type': metadata['model_type'],
        'task': metadata['task'],
        'num_classes': metadata['num_classes'],
        'n_channels': metadata['n_channels'],
        'window_ms': metadata['window_ms'],
        'norm_params': metadata['norm_params'],
        'pretrained_from': args.pretrained,
        'freeze_features': args.freeze_features,
        'history': history,
        'best_val_acc': max(history['val_acc']),
    }

    # Save state_dict only for direct compatibility with model_train.py outputs.
    torch.save(model.state_dict(), model_path)

    # Save metadata checkpoint alongside for reproducibility/debugging.
    metadata_model_path = output_dir / f"{metadata['model_type']}_{args.acquisition_type}_metadata.pth"
    torch.save(save_dict, metadata_model_path)

    # Save matched labels encoder in the same naming convention expected by active decoding.
    labels_encoder = LabelEncoder()
    labels_encoder.fit(y)
    data_subject_dir = Path('data') / args.subj_type / f'S{args.subj}'
    data_subject_dir.mkdir(parents=True, exist_ok=True)
    labels_encoder_path = data_subject_dir / f"{args.acquisition_type}_{task_name}_labels_encoder.pkl"
    with open(labels_encoder_path, 'wb') as f:
        pickle.dump({'labels_encoder': labels_encoder}, f)

    print(f"\n✅ Fine-tuned model saved to: {model_path}")
    print(f"✅ Metadata checkpoint saved to: {metadata_model_path}")
    print(f"✅ Matched labels encoder saved to: {labels_encoder_path}")
    
    # Summary
    print("\n" + "="*60)
    print("📊 Fine-tuning Summary")
    print("="*60)
    print(f"  Pre-trained accuracy: {metadata['best_val_acc']:.2%}")
    print(f"  Fine-tuned accuracy: {max(history['val_acc']):.2%}")
    print(f"  Improvement: {max(history['val_acc']) - metadata['best_val_acc']:.2%}")
    print("="*60 + "\n")


if __name__ == '__main__':
    main()
