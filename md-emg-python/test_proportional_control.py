"""
Test Script for Proportional Control System
==========================================

This script tests the proportional control decoders and motor unit decomposition
without requiring live EMG hardware.
"""

import numpy as np
import torch
import time
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from models.proportional_decoders import (
    MLPProportionalDecoder,
    KNNProportionalDecoder,
    ProportionalControlMapper
)
from utils.motor_unit_decomposition import (
    MotorUnitDecomposer,
    get_mud_features
)


def test_mlp_decoder():
    """Test MLP proportional decoder"""
    print("\n" + "="*60)
    print("Testing MLP Proportional Decoder")
    print("="*60)
    
    # Create decoder
    input_dim = 64  # 64 EMG channels
    output_dim = 10  # 5 fingers x 2 directions
    
    decoder = MLPProportionalDecoder(
        input_dim=input_dim,
        hidden_dims=[256, 128, 64],
        output_dim=output_dim,
        dropout=0.3
    )
    
    decoder.eval()
    
    print(f"✓ MLP decoder created: {input_dim} inputs -> {output_dim} outputs")
    print(f"  Architecture: {input_dim} -> 256 -> 128 -> 64 -> {output_dim}")
    
    # Test forward pass
    batch_size = 5
    test_input = torch.randn(batch_size, input_dim)
    
    with torch.no_grad():
        output = decoder(test_input)
    
    print(f"✓ Forward pass successful")
    print(f"  Input shape: {test_input.shape}")
    print(f"  Output shape: {output.shape}")
    print(f"  Output range: [{output.min():.3f}, {output.max():.3f}]")
    
    # Check output is in valid range
    assert torch.all(output >= 0) and torch.all(output <= 1), "Output should be in [0, 1]"
    print(f"✓ Output values are in valid range [0, 1]")
    
    # Test sequential input
    seq_input = torch.randn(batch_size, 20, input_dim)  # (batch, time, features)
    with torch.no_grad():
        seq_output = decoder(seq_input)
    
    print(f"✓ Sequential input handling works")
    print(f"  Sequential input shape: {seq_input.shape}")
    print(f"  Sequential output shape: {seq_output.shape}")
    
    return decoder


def test_knn_decoder():
    """Test KNN proportional decoder"""
    print("\n" + "="*60)
    print("Testing KNN Proportional Decoder")
    print("="*60)
    
    # Create decoder
    output_dim = 10
    decoder = KNNProportionalDecoder(
        n_neighbors=5,
        weights='distance',
        output_dim=output_dim
    )
    
    print(f"✓ KNN decoder created: n_neighbors={decoder.n_neighbors}, weights={decoder.weights}")
    
    # Generate synthetic training data
    n_samples = 200
    n_features = 64
    
    X_train = np.random.randn(n_samples, n_features)
    y_train = np.random.rand(n_samples, output_dim)
    
    print(f"✓ Generated synthetic training data: {X_train.shape}, {y_train.shape}")
    
    # Fit decoder
    start_time = time.time()
    decoder.fit(X_train, y_train)
    fit_time = time.time() - start_time
    
    print(f"✓ Decoder fitted in {fit_time:.3f}s")
    
    # Test prediction
    X_test = np.random.randn(10, n_features)
    
    start_time = time.time()
    predictions = decoder.predict(X_test)
    pred_time = time.time() - start_time
    
    print(f"✓ Predictions successful")
    print(f"  Test input shape: {X_test.shape}")
    print(f"  Predictions shape: {predictions.shape}")
    print(f"  Prediction time: {pred_time*1000:.2f}ms for {len(X_test)} samples")
    print(f"  Prediction range: [{predictions.min():.3f}, {predictions.max():.3f}]")
    
    # Check output is in valid range
    assert np.all(predictions >= 0) and np.all(predictions <= 1), "Output should be in [0, 1]"
    print(f"✓ Output values are in valid range [0, 1]")
    
    return decoder


def test_proportional_control_mapper():
    """Test proportional control mapper"""
    print("\n" + "="*60)
    print("Testing Proportional Control Mapper")
    print("="*60)
    
    # Test individual fingers mode
    print("\n--- Individual Fingers Mode ---")
    mapper = ProportionalControlMapper(control_mode='individual_fingers', num_fingers=5)
    
    print(f"✓ Mapper created: {mapper.control_mode} mode, {mapper.num_fingers} fingers")
    print(f"  Output dimension: {mapper.output_dim}")
    
    # Generate test proportional values
    proportional_values = np.random.rand(mapper.output_dim)
    
    # Decode to finger control
    finger_control = mapper.decode_output(proportional_values)
    
    print(f"✓ Decoded proportional values to finger control")
    print(f"  Input shape: {proportional_values.shape}")
    print(f"  Output keys: {list(finger_control.keys())}")
    
    # Check structure
    for finger, control in finger_control.items():
        assert 'flexion' in control and 'extension' in control
        assert 'speed' in control and 'force' in control
        print(f"  {finger}: flex={control['flexion']:.3f}, ext={control['extension']:.3f}, " + 
              f"speed={control['speed']:.3f}, force={control['force']:.3f}")
    
    # Test Unity format conversion
    unity_format = mapper.to_unity_format(finger_control)
    print(f"✓ Converted to Unity format")
    print(f"  Control type: {unity_format['control_type']}")
    print(f"  Number of fingers: {len(unity_format['fingers'])}")
    
    # Test ESP32 format conversion
    esp32_format = mapper.to_esp32_format(finger_control)
    print(f"✓ Converted to ESP32 format")
    print(f"  Control type: {esp32_format['control_type']}")
    
    # Show ESP32 values for first finger
    first_finger = list(esp32_format['fingers'].keys())[0]
    first_control = esp32_format['fingers'][first_finger]
    print(f"  Example ({first_finger}): flex_pressure={first_control['flexion_pressure']}, " +
          f"ext_pressure={first_control['extension_pressure']}, speed={first_control['speed']}")
    
    # Test whole-hand mode
    print("\n--- Whole Hand Mode ---")
    mapper_whole = ProportionalControlMapper(control_mode='whole_hand', num_fingers=5)
    
    print(f"✓ Mapper created: {mapper_whole.control_mode} mode")
    print(f"  Output dimension: {mapper_whole.output_dim}")
    
    proportional_values_whole = np.random.rand(mapper_whole.output_dim)
    finger_control_whole = mapper_whole.decode_output(proportional_values_whole)
    
    print(f"✓ Decoded whole-hand control")
    print(f"  All fingers have same values: {all(f['flexion'] == finger_control_whole['thumb']['flexion'] for f in finger_control_whole.values())}")
    
    return mapper


def test_motor_unit_decomposition():
    """Test motor unit decomposition"""
    print("\n" + "="*60)
    print("Testing Motor Unit Decomposition")
    print("="*60)
    
    # Create decomposer
    fsample = 2048
    decomposer = MotorUnitDecomposer(
        fsample=fsample,
        threshold_method='mad',
        spike_detection_threshold=4.0
    )
    
    print(f"✓ MUD decomposer created")
    print(f"  Sampling frequency: {decomposer.fsample} Hz")
    print(f"  Threshold method: {decomposer.threshold_method}")
    print(f"  Spike threshold: {decomposer.spike_detection_threshold}")
    
    # Generate synthetic EMG signal
    duration = 1.0  # seconds
    n_samples = int(duration * fsample)
    n_channels = 64
    
    # Simulate EMG with some spikes
    signal_data = np.random.randn(n_samples, n_channels) * 0.1
    
    # Add some synthetic spikes
    spike_times = [int(0.1*fsample), int(0.3*fsample), int(0.5*fsample), int(0.7*fsample)]
    for spike_time in spike_times:
        if spike_time < n_samples:
            signal_data[spike_time:spike_time+10, 0] += 0.5  # Add spike to first channel
    
    print(f"✓ Generated synthetic EMG signal: {signal_data.shape}")
    print(f"  Duration: {duration}s, Channels: {n_channels}")
    
    # Preprocess signal
    preprocessed = decomposer.preprocess_signal(signal_data)
    print(f"✓ Signal preprocessed: {preprocessed.shape}")
    
    # Detect spikes
    spikes = decomposer.detect_spikes(preprocessed, channel_idx=0)
    print(f"✓ Spikes detected: {len(spikes)} spikes in channel 0")
    
    # Extract features
    features = decomposer.decompose_to_features(signal_data, n_units=5)
    print(f"✓ Features extracted: {features.shape}")
    print(f"  Feature range: [{features.min():.3f}, {features.max():.3f}]")
    
    # Test get_mud_features convenience function
    print("\n--- Testing get_mud_features function ---")
    
    # With MUD
    features_mud = get_mud_features(signal_data, fsample=fsample, use_mud=True)
    print(f"✓ MUD features: {features_mud.shape}")
    
    # Without MUD (raw RMS)
    features_raw = get_mud_features(signal_data, fsample=fsample, use_mud=False)
    print(f"✓ Raw RMS features: {features_raw.shape}")
    
    return decomposer


def test_integration():
    """Test full integration of components"""
    print("\n" + "="*60)
    print("Testing Full Integration")
    print("="*60)
    
    # Setup
    fsample = 2048
    n_samples = 2048  # 1 second
    n_channels = 64
    
    print("Simulating complete proportional control pipeline...")
    
    # 1. Generate synthetic EMG
    emg_signal = np.random.randn(n_samples, n_channels) * 0.1
    print(f"✓ Step 1: Generated EMG signal {emg_signal.shape}")
    
    # 2. Extract features (with MUD)
    features = get_mud_features(emg_signal, fsample=fsample, use_mud=True)
    print(f"✓ Step 2: Extracted features {features.shape}")
    
    # 3. Create and use MLP decoder
    decoder = MLPProportionalDecoder(
        input_dim=len(features),
        hidden_dims=[128, 64],
        output_dim=10
    )
    decoder.eval()
    
    features_tensor = torch.tensor(features, dtype=torch.float32).unsqueeze(0)
    with torch.no_grad():
        proportional_output = decoder(features_tensor).numpy()[0]
    
    print(f"✓ Step 3: Decoded to proportional values {proportional_output.shape}")
    print(f"  Output range: [{proportional_output.min():.3f}, {proportional_output.max():.3f}]")
    
    # 4. Map to finger control
    mapper = ProportionalControlMapper(control_mode='individual_fingers', num_fingers=5)
    finger_control = mapper.decode_output(proportional_output)
    
    print(f"✓ Step 4: Mapped to finger control")
    print(f"  Number of fingers: {len(finger_control)}")
    
    # 5. Convert to Unity and ESP32 formats
    unity_format = mapper.to_unity_format(finger_control)
    esp32_format = mapper.to_esp32_format(finger_control)
    
    print(f"✓ Step 5: Converted to output formats")
    print(f"  Unity format ready: {unity_format['control_type']}")
    print(f"  ESP32 format ready: {esp32_format['control_type']}")
    
    # Display sample output
    print("\n--- Sample Finger Control Output ---")
    for finger_name in ['thumb', 'index', 'middle']:
        control = finger_control[finger_name]
        print(f"{finger_name.capitalize()}: flex={control['flexion']:.2f}, ext={control['extension']:.2f}, " +
              f"speed={control['speed']:.2f}, force={control['force']:.2f}")
    
    print("\n✓ Full integration test successful!")


def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("PROPORTIONAL CONTROL SYSTEM TEST SUITE")
    print("="*60)
    
    try:
        # Test individual components
        test_mlp_decoder()
        test_knn_decoder()
        test_proportional_control_mapper()
        test_motor_unit_decomposition()
        
        # Test integration
        test_integration()
        
        print("\n" + "="*60)
        print("ALL TESTS PASSED ✓")
        print("="*60)
        
    except Exception as e:
        print(f"\n✗ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
