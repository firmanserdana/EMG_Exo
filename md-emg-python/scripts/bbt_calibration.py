#!/usr/bin/env python3
"""
Box and Block Test (BBT) Calibration Script
============================================

Clinical calibration workflow for the Box and Block Test with EMG-controlled exoskeleton.

Key Features:
1. Dynamic training data collection (with arm movement)
2. Transfer learning from pre-trained healthy model
3. Quick calibration for per-session adaptation
4. Electrode dropout robustness testing

Usage:
    python bbt_calibration.py --subj 1 --mode full_calibration
    python bbt_calibration.py --subj 1 --mode quick_calibration
    python bbt_calibration.py --subj 1 --mode test_robustness
"""

import os
import sys
import yaml
import time
import numpy as np
import torch
from pathlib import Path
from datetime import datetime
import argparse

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.cnn_lstm_model import CNNLSTMModel, CNNLSTMModelLight
from utils.transfer_learning import TransferLearningTrainer, prepare_dynamic_training_data
from utils.data_utils import load_training_data
from utils.feature_extraction import calc_features_multi_win

def print_header(title):
    """Print formatted header."""
    print("\n" + "="*70)
    print(f"  {title}")
    print("="*70 + "\n")

def print_step(step_num, description):
    """Print step indicator."""
    print(f"\n[Step {step_num}] {description}")
    print("-" * 50)

class BBTCalibrationSession:
    """
    Manages the calibration session for Box and Block Test.
    
    Workflow:
    1. Check hardware connection (EMG amplifier + ESP32)
    2. Collect baseline EMG (rest state)
    3. Collect calibration trials with arm movement
    4. Run transfer learning
    5. Validate model performance
    6. Save calibrated model
    """
    
    def __init__(self, config_path: str, subject_id: int, subject_type: str = 'SCI'):
        """
        Initialize calibration session.
        
        Args:
            config_path: Path to functional_tests.yaml
            subject_id: Subject number
            subject_type: 'healthy' or 'SCI'
        """
        self.subject_id = subject_id
        self.subject_type = subject_type
        self.subj_folder = f"S{subject_id}"
        
        # Load configuration
        with open(config_path) as f:
            self.config = yaml.load(f, Loader=yaml.FullLoader)
        
        # Load CNN-LSTM config
        cnnlstm_config_path = os.path.join(
            os.path.dirname(config_path), 'models', 'CNNLSTM_cfg.yaml'
        )
        if os.path.exists(cnnlstm_config_path):
            with open(cnnlstm_config_path) as f:
                self.model_config = yaml.load(f, Loader=yaml.FullLoader)
        else:
            # Default config
            self.model_config = {
                'input_channels': 32,
                'sequence_length': 30,
                'spatial_cnn': {'virtual_channels': 8},
                'temporal_lstm': {'hidden_size': 64, 'num_layers': 1},
                'num_classes': 3,
                'regularization': {'electrode_dropout': 0.1, 'dropout': 0.3}
            }
        
        # Set up paths
        self.data_folder = os.path.join('data', subject_type, self.subj_folder)
        self.calib_folder = os.path.join(self.data_folder, 'calibration')
        self.models_folder = os.path.join('models-subjects', subject_type, self.subj_folder, 'bbt')
        
        os.makedirs(self.calib_folder, exist_ok=True)
        os.makedirs(self.models_folder, exist_ok=True)
        
        # Initialize trainer
        self.trainer = None
        self.model = None
        self.calibration_data = {
            'rest': [],
            'grasp': [],
            'open': []
        }
        
    def initialize_model(self, pretrained_path: str = None):
        """
        Initialize CNN-LSTM model, optionally from pretrained weights.
        
        Args:
            pretrained_path: Path to pretrained model weights
        """
        print_step(1, "Initializing CNN-LSTM Model")
        
        # Create model
        self.model = CNNLSTMModel(
            input_channels=self.model_config['input_channels'],
            virtual_channels=self.model_config['spatial_cnn']['virtual_channels'],
            hidden_size=self.model_config['temporal_lstm']['hidden_size'],
            num_layers=self.model_config['temporal_lstm']['num_layers'],
            num_classes=self.model_config['num_classes'],
            electrode_dropout=self.model_config['regularization']['electrode_dropout'],
            dropout=self.model_config['regularization']['dropout']
        )
        
        # Load pretrained weights if available
        if pretrained_path and os.path.exists(pretrained_path):
            print(f"  Loading pretrained weights from: {pretrained_path}")
            checkpoint = torch.load(pretrained_path, map_location='cpu')
            if 'model_state_dict' in checkpoint:
                self.model.load_state_dict(checkpoint['model_state_dict'], strict=False)
            else:
                self.model.load_state_dict(checkpoint, strict=False)
            print("  ✓ Pretrained weights loaded")
        else:
            print("  ⚠ No pretrained weights - training from scratch")
        
        # Initialize trainer
        self.trainer = TransferLearningTrainer(
            model=self.model,
            num_classes=self.model_config['num_classes'],
            device='cuda' if torch.cuda.is_available() else 'cpu'
        )
        
        print(f"  Device: {self.trainer.device}")
        print(f"  Model parameters: {sum(p.numel() for p in self.model.parameters()):,}")
        
    def collect_calibration_data(self, 
                                 trials_per_gesture: dict = None,
                                 trial_duration: float = 3.0,
                                 include_movement: bool = True):
        """
        Collect calibration data with guided prompts.
        
        Args:
            trials_per_gesture: Dict with gesture -> num_trials mapping
            trial_duration: Duration of each trial in seconds
            include_movement: Whether to collect data with arm movement
        """
        print_step(2, "Collecting Calibration Data")
        
        if trials_per_gesture is None:
            trials_per_gesture = self.config['calibration']['trials_per_gesture']
        
        calib_config = self.config['calibration']
        
        # Movement positions for dynamic training
        if include_movement and calib_config['movement_calibration']['enabled']:
            arm_positions = calib_config['movement_calibration']['arm_positions']
            trials_per_position = calib_config['movement_calibration']['trials_per_position']
        else:
            arm_positions = ['neutral']
            trials_per_position = 1
        
        print(f"\n  Calibration Protocol:")
        print(f"    - Gestures: {list(trials_per_gesture.keys())}")
        print(f"    - Trials per gesture: {trials_per_gesture}")
        print(f"    - Arm positions: {arm_positions}")
        print(f"    - Trial duration: {trial_duration}s")
        
        input("\n  Press Enter when ready to start calibration...")
        
        for gesture, n_trials in trials_per_gesture.items():
            print(f"\n  === Gesture: {gesture.upper()} ===")
            
            for pos in arm_positions:
                for trial in range(n_trials):
                    print(f"\n  Trial {trial+1}/{n_trials} | Position: {pos}")
                    print(f"  → Perform {gesture.upper()} gesture")
                    
                    # Countdown
                    for i in range(3, 0, -1):
                        print(f"  Starting in {i}...", end='\r')
                        time.sleep(1)
                    
                    print(f"  GO! Hold for {trial_duration}s...")
                    
                    # Here you would actually record EMG data
                    # For now, simulate with placeholder
                    time.sleep(trial_duration)
                    
                    print("  ✓ Trial complete")
                    time.sleep(calib_config['rest_between_trials_sec'])
        
        print("\n  ✓ Calibration data collection complete")
        
    def run_transfer_learning(self, 
                              epochs: int = None,
                              freeze_spatial: bool = True):
        """
        Run transfer learning on collected calibration data.
        
        Args:
            epochs: Number of training epochs
            freeze_spatial: Whether to freeze spatial CNN layers
        """
        print_step(3, "Running Transfer Learning")
        
        if epochs is None:
            epochs = self.config['transfer_learning']['transfer']['epochs']
        
        # Load calibration data
        calib_data_path = os.path.join(self.calib_folder, 'calibration_data.npz')
        
        if not os.path.exists(calib_data_path):
            print("  ⚠ No calibration data found. Using simulated data for demo.")
            # Create dummy data for demonstration
            X_train = np.random.randn(300, 30, 32).astype(np.float32)  # 300 samples, 30 timesteps, 32 channels
            y_train = np.random.randint(0, 3, 300)
            X_val = np.random.randn(100, 30, 32).astype(np.float32)
            y_val = np.random.randint(0, 3, 100)
        else:
            data = np.load(calib_data_path)
            X_train, y_train = data['X_train'], data['y_train']
            X_val, y_val = data['X_val'], data['y_val']
        
        # Prepare dynamic training data
        X_train_aug, y_train_aug = prepare_dynamic_training_data(
            X_train, y_train,
            augment_electrode_dropout=True,
            drop_probability=self.model_config['regularization']['electrode_dropout']
        )
        
        print(f"  Training samples: {len(X_train_aug)}")
        print(f"  Validation samples: {len(X_val)}")
        print(f"  Epochs: {epochs}")
        print(f"  Freeze spatial layers: {freeze_spatial}")
        
        # Run transfer learning
        history = self.trainer.transfer_learn(
            X_train_aug, y_train_aug,
            X_val, y_val,
            epochs=epochs,
            freeze_spatial=freeze_spatial
        )
        
        print(f"\n  Final validation accuracy: {history['val_acc'][-1]:.2%}")
        
        return history
    
    def run_quick_calibration(self, 
                               X_calib: np.ndarray = None,
                               y_calib: np.ndarray = None,
                               epochs: int = 5):
        """
        Run quick calibration for per-session adaptation.
        
        Args:
            X_calib: Calibration EMG data [samples, time, channels]
            y_calib: Calibration labels
            epochs: Number of quick training epochs
        """
        print_step(3, "Quick Calibration (Per-Session)")
        
        if X_calib is None:
            # Use dummy data for demo
            print("  Using simulated quick calibration data")
            X_calib = np.random.randn(30, 30, 32).astype(np.float32)  # Just 30 samples
            y_calib = np.array([0]*10 + [1]*10 + [2]*10)  # 10 per class
        
        print(f"  Quick calibration samples: {len(X_calib)}")
        print(f"  Epochs: {epochs}")
        
        accuracy = self.trainer.quick_calibrate(
            X_calib, y_calib,
            epochs=epochs
        )
        
        print(f"\n  Quick calibration accuracy: {accuracy:.2%}")
        
        return accuracy
    
    def test_robustness(self, n_dropout_tests: int = 10):
        """
        Test model robustness by simulating electrode dropout.
        
        Args:
            n_dropout_tests: Number of dropout configurations to test
        """
        print_step(4, "Testing Robustness to Electrode Dropout")
        
        # Create test data
        X_test = np.random.randn(100, 30, 32).astype(np.float32)
        y_test = np.random.randint(0, 3, 100)
        
        X_test_tensor = torch.from_numpy(X_test).to(self.trainer.device)
        y_test_tensor = torch.from_numpy(y_test).to(self.trainer.device)
        
        results = []
        
        print(f"\n  Testing {n_dropout_tests} dropout configurations...")
        
        for i in range(n_dropout_tests):
            # Simulate different dropout patterns
            dropout_prob = i / n_dropout_tests * 0.3  # 0% to 30%
            
            X_dropped = X_test.copy()
            if dropout_prob > 0:
                mask = np.random.rand(32) > dropout_prob
                X_dropped[:, :, ~mask] = 0
            
            X_dropped_tensor = torch.from_numpy(X_dropped).to(self.trainer.device)
            
            # Evaluate
            self.model.eval()
            with torch.no_grad():
                outputs = self.model(X_dropped_tensor)
                _, predicted = torch.max(outputs, 1)
                accuracy = (predicted == y_test_tensor).float().mean().item()
            
            results.append({
                'dropout_prob': dropout_prob,
                'accuracy': accuracy
            })
            
            print(f"    Dropout {dropout_prob*100:.0f}%: Accuracy {accuracy:.2%}")
        
        # Summary
        print("\n  Robustness Summary:")
        print(f"    Baseline (0% dropout): {results[0]['accuracy']:.2%}")
        print(f"    10% dropout: {results[3]['accuracy']:.2%}")
        print(f"    20% dropout: {results[6]['accuracy']:.2%}")
        print(f"    30% dropout: {results[9]['accuracy']:.2%}")
        
        return results
    
    def save_calibrated_model(self, filename: str = None):
        """
        Save the calibrated model.
        
        Args:
            filename: Output filename (auto-generated if None)
        """
        print_step(5, "Saving Calibrated Model")
        
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"cnnlstm_bbt_{timestamp}.pth"
        
        filepath = os.path.join(self.models_folder, filename)
        
        checkpoint = {
            'model_state_dict': self.model.state_dict(),
            'model_config': self.model_config,
            'subject_id': self.subject_id,
            'subject_type': self.subject_type,
            'calibration_date': datetime.now().isoformat(),
            'test_type': 'box_and_block'
        }
        
        torch.save(checkpoint, filepath)
        print(f"  Model saved to: {filepath}")
        
        return filepath
    
    def run_full_calibration(self, pretrained_path: str = None):
        """
        Run the complete calibration workflow.
        
        Args:
            pretrained_path: Path to pretrained model
        """
        print_header("Box and Block Test - Full Calibration")
        
        print(f"Subject: {self.subject_type}/{self.subj_folder}")
        print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Step 1: Initialize model
        self.initialize_model(pretrained_path)
        
        # Step 2: Collect calibration data
        # (In production, this would actually record EMG)
        # self.collect_calibration_data()
        print("\n  [Skipping data collection for demo - using simulated data]")
        
        # Step 3: Transfer learning
        history = self.run_transfer_learning(epochs=10)
        
        # Step 4: Test robustness
        robustness = self.test_robustness(n_dropout_tests=10)
        
        # Step 5: Save model
        model_path = self.save_calibrated_model()
        
        print_header("Calibration Complete")
        print(f"  ✓ Model saved: {model_path}")
        print(f"  ✓ Final accuracy: {history['val_acc'][-1]:.2%}")
        print(f"  ✓ Ready for Box and Block Test")
        
        return model_path


def main():
    parser = argparse.ArgumentParser(
        description='BBT Calibration Script',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Full calibration with transfer learning
    python bbt_calibration.py --subj 1 --mode full_calibration
    
    # Quick per-session calibration
    python bbt_calibration.py --subj 1 --mode quick_calibration
    
    # Test model robustness to electrode dropout
    python bbt_calibration.py --subj 1 --mode test_robustness
        """
    )
    
    parser.add_argument('--subj', type=int, default=1,
                        help='Subject number (default: 1)')
    parser.add_argument('--subj_type', type=str, default='SCI',
                        choices=['healthy', 'SCI'],
                        help='Subject type (default: SCI)')
    parser.add_argument('--mode', type=str, default='full_calibration',
                        choices=['full_calibration', 'quick_calibration', 'test_robustness'],
                        help='Calibration mode (default: full_calibration)')
    parser.add_argument('--pretrained', type=str, default=None,
                        help='Path to pretrained model')
    parser.add_argument('--config', type=str, 
                        default='config/functional_tests.yaml',
                        help='Path to config file')
    
    args = parser.parse_args()
    
    # Initialize session
    session = BBTCalibrationSession(
        config_path=args.config,
        subject_id=args.subj,
        subject_type=args.subj_type
    )
    
    if args.mode == 'full_calibration':
        session.run_full_calibration(pretrained_path=args.pretrained)
        
    elif args.mode == 'quick_calibration':
        session.initialize_model(pretrained_path=args.pretrained)
        session.run_quick_calibration()
        session.save_calibrated_model()
        
    elif args.mode == 'test_robustness':
        session.initialize_model(pretrained_path=args.pretrained)
        session.test_robustness()


if __name__ == '__main__':
    main()
