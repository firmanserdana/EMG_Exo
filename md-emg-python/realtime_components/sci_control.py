"""
SCI Patient Control Module
==========================

Specialized control logic for Spinal Cord Injury patients using EMG-controlled
exoskeletons. Implements hybrid control, spasticity management, and fatigue
compensation to address the unique challenges of SCI.

Key Features:
- Hybrid control (EMG triggers, robot executes trajectory)
- Spasticity detection and suppression
- Fatigue compensation with adaptive thresholds
- Motion artifact rejection
- Safety limits and emergency stop

Usage:
------
from realtime_components.sci_control import SCIControlLoop

# In main script:
p_control = Process(
    target=SCIControlLoop,
    args=(events_socket, control_params, pred_queue, stop_program, esp32_queue, sci_cfg)
)
"""

import time
import json
import threading
import yaml
import numpy as np
from collections import deque
from queue import Full, Empty

from utils.signal_filtering import (
    SpasticityDetector,
    FatigueCompensator,
    BlankingFilter
)


class HybridController:
    """
    Hybrid control mode for SCI patients.
    
    EMG is used to trigger actions, but the robot handles trajectory execution.
    This reduces the continuous control burden on the patient and provides
    smoother, more predictable movements.
    """
    
    def __init__(self, config):
        self.config = config
        self.trigger_config = config.get('trigger_mode', {})
        self.trajectory_config = config.get('shared_autonomy', {}).get('trajectories', {})
        
        # Trigger state
        self.trigger_type = self.trigger_config.get('type', 'threshold')
        self.activation_threshold = self.trigger_config.get('threshold', {}).get('activation', 0.3)
        self.deactivation_threshold = self.trigger_config.get('threshold', {}).get('deactivation', 0.15)
        self.use_hysteresis = self.trigger_config.get('threshold', {}).get('hysteresis', True)
        
        # Sustained activation tracking
        self.sustained_duration = self.trigger_config.get('sustained', {}).get('duration_ms', 300) / 1000
        self.sustained_start_time = None
        self.sustained_active = False
        
        # Current trajectory state
        self.current_trajectory = None
        self.trajectory_start_time = None
        self.trajectory_active = False
        
        # State machine
        self.state = 'idle'  # idle, triggered, executing, holding
        self.last_trigger_time = 0
        self.triggered_gesture = None
    
    def process_prediction(self, prediction, confidence, emg_amplitude, current_time):
        """
        Process prediction through hybrid control logic.
        
        Parameters:
        -----------
        prediction : int
            Decoded gesture prediction
        confidence : float
            Prediction confidence
        emg_amplitude : float
            Current EMG amplitude (normalized)
        current_time : float
            Current timestamp
            
        Returns:
        --------
        action : dict
            Action to execute: {'type': 'trigger'|'hold'|'release'|'none',
                               'gesture': int, 'trajectory': dict}
        """
        action = {'type': 'none', 'gesture': None, 'trajectory': None}
        
        # State machine logic
        if self.state == 'idle':
            # Check for trigger condition
            if self._check_trigger(prediction, confidence, emg_amplitude, current_time):
                self.state = 'triggered'
                self.triggered_gesture = prediction
                self.last_trigger_time = current_time
                action['type'] = 'trigger'
                action['gesture'] = prediction
                action['trajectory'] = self._get_trajectory(prediction)
                print(f"   🎯 Hybrid trigger: gesture {prediction}")
                
        elif self.state == 'triggered':
            # Start trajectory execution
            self.state = 'executing'
            self.trajectory_start_time = current_time
            self.trajectory_active = True
            action['type'] = 'execute'
            action['gesture'] = self.triggered_gesture
            
        elif self.state == 'executing':
            # Check trajectory completion
            trajectory = self._get_trajectory(self.triggered_gesture)
            duration = trajectory.get('duration_ms', 500) / 1000
            
            if current_time - self.trajectory_start_time >= duration:
                self.state = 'holding'
                action['type'] = 'hold'
                action['gesture'] = self.triggered_gesture
                print(f"   ✋ Trajectory complete, holding")
            else:
                action['type'] = 'executing'
                action['gesture'] = self.triggered_gesture
                
        elif self.state == 'holding':
            # Check for release condition
            if self._check_release(emg_amplitude):
                self.state = 'idle'
                self.triggered_gesture = None
                self.trajectory_active = False
                action['type'] = 'release'
                action['gesture'] = 0  # Rest/release
                print(f"   👐 Release detected, returning to idle")
        
        return action
    
    def _check_trigger(self, prediction, confidence, emg_amplitude, current_time):
        """Check if trigger condition is met."""
        if prediction == 0:  # Rest is not a trigger
            self.sustained_start_time = None
            return False
        
        if self.trigger_type == 'threshold':
            return emg_amplitude >= self.activation_threshold and confidence >= 0.3
            
        elif self.trigger_type == 'sustained':
            if emg_amplitude >= self.activation_threshold:
                if self.sustained_start_time is None:
                    self.sustained_start_time = current_time
                elif current_time - self.sustained_start_time >= self.sustained_duration:
                    self.sustained_start_time = None
                    return True
            else:
                self.sustained_start_time = None
            return False
        
        return False
    
    def _check_release(self, emg_amplitude):
        """Check if release condition is met."""
        return emg_amplitude < self.deactivation_threshold
    
    def _get_trajectory(self, gesture):
        """Get trajectory parameters for gesture."""
        gesture_names = {
            1: 'hand_open',
            2: 'hand_close',
            0: 'rest'
        }
        name = gesture_names.get(gesture, 'hand_close')
        return self.trajectory_config.get(name, {'duration_ms': 500, 'profile': 'smooth'})
    
    def reset(self):
        """Reset controller state."""
        self.state = 'idle'
        self.triggered_gesture = None
        self.trajectory_active = False
        self.sustained_start_time = None


class SCIControlLoop:
    """
    Main control loop for SCI patients.
    
    Integrates all SCI-specific features:
    - Hybrid control mode
    - Spasticity detection
    - Fatigue compensation
    - Safety monitoring
    """
    pass


def SCIControlLoop(
    events_socket,
    control_params,
    pred_control_queue,
    stop_program,
    pred_esp32_queue=None,
    unity_events_queue=None,
    sci_config=None
):
    """
    SCI-specific control loop with hybrid control and safety features.
    
    Parameters:
    -----------
    events_socket : socket
        Socket for Unity communication
    control_params : dict
        Control parameters
    pred_control_queue : Queue
        Queue receiving predictions from decoder
    stop_program : Value
        Shared value to signal program stop
    pred_esp32_queue : Queue, optional
        Queue for ESP32 commands
    unity_events_queue : Queue, optional
        Queue for Unity events
    sci_config : dict, optional
        SCI-specific configuration
    """
    print('Starting SCI Control Loop...')
    print('  ✓ Hybrid control mode enabled')
    print('  ✓ Spasticity detection active')
    print('  ✓ Fatigue compensation active')
    
    # Load default config if not provided
    if sci_config is None:
        try:
            with open('config/sci_patient.yaml', 'r') as f:
                sci_config = yaml.safe_load(f)
        except FileNotFoundError:
            print("  ⚠️  SCI config not found, using defaults")
            sci_config = {}
    
    # Initialize components
    n_channels = control_params.get('num_channels', 32)
    fsample = control_params.get('fsample', 1000)
    task_name = control_params.get('task', 'open_close')
    
    # Spasticity detector
    spasticity_cfg = sci_config.get('spasticity', {}).get('detection', {})
    spasticity_detector = SpasticityDetector(
        n_channels=n_channels,
        fsample=fsample,
        threshold_factor=spasticity_cfg.get('threshold_factor', 3.0),
        rise_time_ms=spasticity_cfg.get('rise_time_ms', 50),
        refractory_ms=spasticity_cfg.get('refractory_ms', 500)
    )
    
    # Fatigue compensator
    fatigue_cfg = sci_config.get('fatigue', {})
    fatigue_compensator = FatigueCompensator(
        n_channels=n_channels,
        window_sec=fatigue_cfg.get('tracking_window_sec', 30),
        fsample=fsample,
        compensation_rate=fatigue_cfg.get('max_compensation_factor', 2.5)
    )
    
    # Hybrid controller
    hybrid_cfg = sci_config.get('hybrid_control', {})
    hybrid_controller = HybridController(hybrid_cfg) if hybrid_cfg.get('enabled', True) else None
    
    # Blanking filter (for motor artifacts)
    blanking_cfg = sci_config.get('signal_enhancement', {}).get('blanking_filter', {})
    blanking_filter = BlankingFilter(
        pre_blank_ms=blanking_cfg.get('pre_blank_ms', 5),
        post_blank_ms=blanking_cfg.get('post_blank_ms', 25),
        fsample=fsample
    ) if blanking_cfg.get('enabled', True) else None
    
    # Prediction filtering settings
    pred_filter_cfg = sci_config.get('prediction_filtering', {})
    min_confidence = pred_filter_cfg.get('min_confidence', 0.5)
    use_consec_pred = pred_filter_cfg.get('consecutive_predictions', {}).get('enabled', True)
    num_consec_pred = pred_filter_cfg.get('consecutive_predictions', {}).get('count', 4)
    
    # Safety settings
    safety_cfg = sci_config.get('safety', {})
    max_force = safety_cfg.get('max_force', 0.7)
    max_speed = safety_cfg.get('max_speed', 3)
    
    # State tracking
    last_ts = time.perf_counter()
    last_predictions = deque([], maxlen=num_consec_pred) if use_consec_pred else None
    last_sent_gesture = None
    emg_amplitude_history = deque(maxlen=100)
    
    # Performance stats
    stats = {
        'predictions_processed': 0,
        'spasms_detected': 0,
        'fatigue_compensations': 0,
        'hybrid_triggers': 0,
        'emergency_stops': 0,
        'start_time': time.perf_counter()
    }
    
    # Unity event mappings (same as standard control)
    unity_event_mappings = {
        'open_close': {1: 0, 2: 1},  # HandOpen, HandClose
        'grasp_patterns': {3: 2, 4: 3, 5: 4},
        'single_fingers': {6: 5, 7: 6, 8: 7},
    }
    
    def send_to_esp32(gesture_id, confidence, timestamp):
        """Send gesture command to ESP32 with safety limits."""
        nonlocal last_sent_gesture
        
        if pred_esp32_queue is None:
            return
        
        # Apply safety limits
        scaled_confidence = min(confidence, max_force)
        
        try:
            pred_esp32_queue.put((gesture_id, scaled_confidence, timestamp), timeout=0.1)
            last_sent_gesture = gesture_id
            print(f"   → ESP32: gesture {gesture_id} (conf: {scaled_confidence:.2f})")
        except Full:
            print(f"   ⚠️  ESP32 queue full")
    
    def send_to_unity(event_id):
        """Send event to Unity."""
        try:
            event = {"eventName": "grasp_decoded", "eventID": int(event_id)}
            events_socket.sendall((json.dumps(event) + '\n').encode())
            print(f"   → Unity: event {event_id}")
        except Exception as e:
            print(f"   ⚠️  Unity send error: {e}")
    
    def emergency_stop(reason):
        """Execute emergency stop."""
        stats['emergency_stops'] += 1
        print(f"\n🚨 EMERGENCY STOP: {reason}")
        
        # Send rest/release to ESP32
        send_to_esp32(0, 1.0, time.perf_counter())
        
        # Reset controllers
        if hybrid_controller:
            hybrid_controller.reset()
        spasticity_detector.reset()
    
    # Main control loop
    print("\n🏥 SCI Control Loop active - waiting for predictions...\n")
    
    while not stop_program.value:
        try:
            data = pred_control_queue.get(timeout=0.1)
        except Empty:
            continue
        
        if data is None:
            break
        
        current_time = time.perf_counter()
        pred = data[0]
        pred_prob = data[1]
        
        # Get EMG amplitude if available (from extended data)
        emg_amplitude = data[3] if len(data) > 3 else pred_prob
        emg_amplitude_history.append(emg_amplitude)
        
        stats['predictions_processed'] += 1
        
        # === Spasticity Detection ===
        # Create dummy EMG sample for spasticity check (use amplitude as proxy)
        dummy_emg = np.ones(n_channels) * emg_amplitude
        is_spasm, spasm_confidence = spasticity_detector.update(dummy_emg, current_time)
        
        if is_spasm:
            stats['spasms_detected'] += 1
            spasm_response = sci_config.get('spasticity', {}).get('response', {})
            
            if spasm_response.get('action') == 'emergency_stop':
                emergency_stop("Spasticity detected")
                continue
            else:
                # Suppress and hold current position
                print(f"   ⚡ Spasm detected (conf: {spasm_confidence:.2f}) - suppressing")
                continue
        
        # === Fatigue Compensation ===
        compensation_factor, fatigue_level = fatigue_compensator.update(
            np.mean(list(emg_amplitude_history)[-10:]) if emg_amplitude_history else 0
        )
        
        if compensation_factor > 1.1:
            stats['fatigue_compensations'] += 1
            adjusted_confidence = min(pred_prob * compensation_factor, 1.0)
            if fatigue_level > 0.3:
                print(f"   💪 Fatigue compensation: {compensation_factor:.2f}x (fatigue: {fatigue_level:.0%})")
        else:
            adjusted_confidence = pred_prob
        
        # === Confidence Check ===
        if adjusted_confidence < min_confidence:
            print(f"   ⚠️  Low confidence ({adjusted_confidence:.2f} < {min_confidence})")
            # Send rest on low confidence
            if last_sent_gesture != 0:
                send_to_esp32(0, 1.0, current_time)
            continue
        
        # === Hybrid Control Processing ===
        if hybrid_controller and hybrid_cfg.get('enabled', True):
            action = hybrid_controller.process_prediction(
                pred, adjusted_confidence, emg_amplitude, current_time
            )
            
            if action['type'] == 'trigger':
                stats['hybrid_triggers'] += 1
                # Notify spasticity detector of impending movement
                spasticity_detector.notify_exo_movement(current_time)
                
                # Trigger blanking filter
                if blanking_filter:
                    blanking_filter.trigger_blank()
                
                # Send to ESP32
                gesture = action['gesture']
                send_to_esp32(gesture, adjusted_confidence, current_time)
                
                # Map to Unity event
                task_mapping = unity_event_mappings.get(task_name, {})
                unity_event = task_mapping.get(pred)
                if unity_event is not None:
                    send_to_unity(unity_event)
                    
            elif action['type'] == 'hold':
                # Continue holding, no new command needed
                pass
                
            elif action['type'] == 'release':
                send_to_esp32(0, 1.0, current_time)
                
        else:
            # Standard control (with consecutive prediction filtering)
            if use_consec_pred:
                last_predictions.append(pred)
                
                if len(last_predictions) == num_consec_pred:
                    if all(p == last_predictions[0] for p in last_predictions):
                        # All predictions match - execute
                        consensus_pred = last_predictions[0]
                        
                        if consensus_pred == 0:
                            send_to_esp32(0, 1.0, current_time)
                        else:
                            send_to_esp32(consensus_pred, adjusted_confidence, current_time)
                            
                            task_mapping = unity_event_mappings.get(task_name, {})
                            unity_event = task_mapping.get(consensus_pred)
                            if unity_event is not None:
                                send_to_unity(unity_event)
                        
                        last_predictions.clear()
            else:
                # Direct control
                if pred == 0:
                    send_to_esp32(0, 1.0, current_time)
                else:
                    send_to_esp32(pred, adjusted_confidence, current_time)
        
        last_ts = current_time
    
    # Print summary statistics
    duration = time.perf_counter() - stats['start_time']
    print(f'\n📊 SCI Control Loop Summary:')
    print(f'   • Duration: {duration:.2f}s')
    print(f'   • Predictions processed: {stats["predictions_processed"]}')
    print(f'   • Spasms detected: {stats["spasms_detected"]}')
    print(f'   • Fatigue compensations: {stats["fatigue_compensations"]}')
    print(f'   • Hybrid triggers: {stats["hybrid_triggers"]}')
    print(f'   • Emergency stops: {stats["emergency_stops"]}')
    
    # Send final rest command
    if pred_esp32_queue is not None and last_sent_gesture != 0:
        send_to_esp32(0, 1.0, time.perf_counter())
    
    print('SCI Control loop stopped')
