"""
Example: Using Proportional Control System
=========================================

This script demonstrates how to use the proportional control system
with synthetic EMG data.
"""

import numpy as np
import torch
import time

from models.proportional_decoders import (
    MLPProportionalDecoder,
    KNNProportionalDecoder,
    ProportionalControlMapper
)
from utils.motor_unit_decomposition import get_mud_features


def example_1_basic_mlp_usage():
    """Example 1: Basic MLP decoder usage"""
    print("\n" + "="*60)
    print("Example 1: Basic MLP Decoder Usage")
    print("="*60)
    
    # Create a simple MLP decoder
    decoder = MLPProportionalDecoder(
        input_dim=64,  # 64 EMG channels
        hidden_dims=[128, 64],
        output_dim=10,  # 5 fingers × 2 directions
        dropout=0.2
    )
    decoder.eval()
    
    # Simulate EMG features (in practice, these come from real EMG)
    emg_features = np.random.randn(64) * 0.1 + 0.5
    emg_tensor = torch.tensor(emg_features, dtype=torch.float32).unsqueeze(0)
    
    # Decode to proportional values
    with torch.no_grad():
        proportional_output = decoder(emg_tensor).numpy()[0]
    
    print(f"✓ EMG features shape: {emg_features.shape}")
    print(f"✓ Proportional output shape: {proportional_output.shape}")
    print(f"✓ Output range: [{proportional_output.min():.3f}, {proportional_output.max():.3f}]")
    
    # Map to finger control
    mapper = ProportionalControlMapper(
        control_mode='individual_fingers',
        num_fingers=5
    )
    
    finger_control = mapper.decode_output(proportional_output)
    
    print(f"\n✓ Decoded to finger control:")
    for finger_name, control in finger_control.items():
        print(f"  {finger_name}: flex={control['flexion']:.2f}, "
              f"ext={control['extension']:.2f}, "
              f"speed={control['speed']:.2f}, "
              f"force={control['force']:.2f}")
    
    return decoder, mapper


def example_2_knn_with_training():
    """Example 2: KNN decoder with training"""
    print("\n" + "="*60)
    print("Example 2: KNN Decoder with Training")
    print("="*60)
    
    # Generate synthetic training data
    n_samples = 100
    n_features = 64
    n_outputs = 10
    
    X_train = np.random.randn(n_samples, n_features)
    y_train = np.random.rand(n_samples, n_outputs)
    
    print(f"✓ Generated training data: X={X_train.shape}, y={y_train.shape}")
    
    # Create and train KNN decoder
    decoder = KNNProportionalDecoder(
        n_neighbors=5,
        weights='distance',
        output_dim=n_outputs
    )
    
    decoder.fit(X_train, y_train)
    print(f"✓ KNN decoder fitted")
    
    # Test prediction
    X_test = np.random.randn(5, n_features)
    predictions = decoder.predict(X_test)
    
    print(f"✓ Predictions shape: {predictions.shape}")
    print(f"✓ Prediction range: [{predictions.min():.3f}, {predictions.max():.3f}]")
    
    return decoder


def example_3_motor_unit_decomposition():
    """Example 3: Motor unit decomposition"""
    print("\n" + "="*60)
    print("Example 3: Motor Unit Decomposition")
    print("="*60)
    
    # Generate synthetic EMG signal
    fsample = 2048
    duration = 1.0  # seconds
    n_samples = int(duration * fsample)
    n_channels = 64
    
    # Simulate EMG with some activity
    emg_signal = np.random.randn(n_samples, n_channels) * 0.1
    
    # Add some synthetic spikes to channel 0
    spike_times = [int(0.2*fsample), int(0.4*fsample), int(0.6*fsample)]
    for spike_time in spike_times:
        emg_signal[spike_time:spike_time+10, 0] += 0.3
    
    print(f"✓ Generated EMG signal: {emg_signal.shape}")
    print(f"  Duration: {duration}s, Channels: {n_channels}")
    
    # Extract features with MUD
    print("\n→ Extracting features with MUD...")
    features_mud = get_mud_features(emg_signal, fsample=fsample, use_mud=True)
    
    print(f"✓ MUD features: {features_mud.shape}")
    print(f"  Feature range: [{features_mud.min():.3f}, {features_mud.max():.3f}]")
    
    # Extract features without MUD (raw RMS)
    print("\n→ Extracting features without MUD (raw RMS)...")
    features_raw = get_mud_features(emg_signal, fsample=fsample, use_mud=False)
    
    print(f"✓ Raw RMS features: {features_raw.shape}")
    print(f"  Feature range: [{features_raw.min():.3f}, {features_raw.max():.3f}]")
    
    return features_mud, features_raw


def example_4_unity_esp32_formats():
    """Example 4: Converting to Unity and ESP32 formats"""
    print("\n" + "="*60)
    print("Example 4: Unity and ESP32 Format Conversion")
    print("="*60)
    
    # Create mapper
    mapper = ProportionalControlMapper(
        control_mode='individual_fingers',
        num_fingers=5
    )
    
    # Generate proportional values
    proportional_values = np.array([
        0.8, 0.2,  # Thumb: high flexion, low extension
        0.3, 0.7,  # Index: low flexion, high extension
        0.5, 0.5,  # Middle: balanced
        0.1, 0.1,  # Ring: minimal
        0.9, 0.1   # Pinky: high flexion
    ])
    
    print(f"✓ Proportional values: {proportional_values.shape}")
    
    # Decode to finger control
    finger_control = mapper.decode_output(proportional_values)
    
    # Convert to Unity format
    unity_format = mapper.to_unity_format(finger_control)
    
    print(f"\n✓ Unity format:")
    print(f"  Control type: {unity_format['control_type']}")
    print(f"  Number of fingers: {len(unity_format['fingers'])}")
    print(f"\n  Example (Thumb):")
    thumb_data = unity_format['fingers']['thumb']
    for key, value in thumb_data.items():
        print(f"    {key}: {value:.3f}")
    
    # Convert to ESP32 format
    esp32_format = mapper.to_esp32_format(finger_control)
    
    print(f"\n✓ ESP32 format:")
    print(f"  Control type: {esp32_format['control_type']}")
    print(f"\n  Example (Index):")
    index_data = esp32_format['fingers']['index']
    for key, value in index_data.items():
        print(f"    {key}: {value}")
    
    return unity_format, esp32_format


def example_5_whole_hand_control():
    """Example 5: Whole-hand control mode"""
    print("\n" + "="*60)
    print("Example 5: Whole-Hand Control Mode")
    print("="*60)
    
    # Create mapper for whole-hand control
    mapper = ProportionalControlMapper(
        control_mode='whole_hand',
        num_fingers=5
    )
    
    print(f"✓ Control mode: {mapper.control_mode}")
    print(f"✓ Output dimension: {mapper.output_dim}")
    
    # Whole-hand control: just 2 values (flexion and extension for all fingers)
    proportional_values = np.array([0.8, 0.2])  # High flexion, low extension
    
    print(f"\n✓ Proportional values: {proportional_values}")
    
    # Decode
    finger_control = mapper.decode_output(proportional_values)
    
    print(f"\n✓ All fingers receive same control:")
    for finger_name, control in list(finger_control.items())[:3]:  # Show first 3
        print(f"  {finger_name}: flex={control['flexion']:.2f}, "
              f"ext={control['extension']:.2f}")
    
    # Verify all fingers have same values
    all_same = all(
        f['flexion'] == finger_control['thumb']['flexion'] 
        for f in finger_control.values()
    )
    print(f"\n✓ All fingers synchronized: {all_same}")
    
    return mapper


def example_6_real_time_simulation():
    """Example 6: Simulate real-time proportional control"""
    print("\n" + "="*60)
    print("Example 6: Real-Time Proportional Control Simulation")
    print("="*60)
    
    # Setup
    decoder = MLPProportionalDecoder(
        input_dim=64,
        hidden_dims=[128, 64],
        output_dim=10
    )
    decoder.eval()
    
    mapper = ProportionalControlMapper(
        control_mode='individual_fingers',
        num_fingers=5
    )
    
    print("✓ Simulating 5 control cycles...")
    print("  (In practice, this runs at 20-50 Hz)")
    
    # Simulate 5 control cycles
    for i in range(5):
        # Simulate EMG features changing over time
        emg_features = np.random.randn(64) * 0.1 + 0.5 + i * 0.05
        emg_tensor = torch.tensor(emg_features, dtype=torch.float32).unsqueeze(0)
        
        # Decode
        start_time = time.time()
        with torch.no_grad():
            proportional_output = decoder(emg_tensor).numpy()[0]
        decode_time = (time.time() - start_time) * 1000
        
        # Map to control
        finger_control = mapper.decode_output(proportional_output)
        unity_format = mapper.to_unity_format(finger_control)
        esp32_format = mapper.to_esp32_format(finger_control)
        
        print(f"\n  Cycle {i+1}:")
        print(f"    Decode time: {decode_time:.2f}ms")
        print(f"    Thumb: flex={finger_control['thumb']['flexion']:.2f}, "
              f"force={finger_control['thumb']['force']:.2f}")
        print(f"    → Unity ready: {unity_format['control_type']}")
        print(f"    → ESP32 ready: {esp32_format['control_type']}")
        
        # Simulate control rate
        time.sleep(0.05)  # 20 Hz
    
    print("\n✓ Real-time simulation complete")


def main():
    """Run all examples"""
    print("\n" + "="*60)
    print("PROPORTIONAL CONTROL USAGE EXAMPLES")
    print("="*60)
    
    try:
        # Run all examples
        example_1_basic_mlp_usage()
        example_2_knn_with_training()
        example_3_motor_unit_decomposition()
        example_4_unity_esp32_formats()
        example_5_whole_hand_control()
        example_6_real_time_simulation()
        
        print("\n" + "="*60)
        print("ALL EXAMPLES COMPLETED SUCCESSFULLY ✓")
        print("="*60)
        
        print("\nNext Steps:")
        print("  1. Collect and prepare your training data")
        print("  2. Train a decoder: python train_proportional_decoder.py")
        print("  3. Run proportional control: python emg_proportional_control.py")
        print("  4. See PROPORTIONAL_CONTROL.md for full documentation")
        
    except Exception as e:
        print(f"\n✗ Example failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == '__main__':
    exit(main())
