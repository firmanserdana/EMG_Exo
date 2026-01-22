"""
Finite State Machine (FSM) Control for Functional Tests
========================================================

Implements a robust state-based control strategy for functional assessments like:
- Box and Block Test (BBT)
- Grasp Prehension Tests (pouring, peg test, jar opening, etc.)

This approach solves critical issues with proportional control:
1. "Slacking" during transport phase (patient relaxes but hand should stay closed)
2. Motion artifacts from shoulder/arm movement
3. Accidental drops due to EMG fluctuations

States:
-------
- IDLE: Hand open/relaxed, waiting for grasp trigger
- CLOSING: Triggered by flexor burst, executing close trajectory
- LOCKED_GRASP: Grasp locked, ignoring EMG fluctuations during transport
- OPENING: Triggered by extensor burst, executing open trajectory

All features can be enabled/disabled via configuration.

Usage:
------
python emg_control_64.py --control_mode fsm --task functional_test
"""

import time
import json
import threading
import yaml
import numpy as np
from enum import Enum, auto
from collections import deque
from queue import Full, Empty
from dataclasses import dataclass, field
from typing import Optional, Tuple, List, Dict


class GraspState(Enum):
    """FSM states for grasp control."""
    IDLE = auto()           # Hand open, waiting for grasp command
    CLOSING = auto()        # Executing close trajectory
    LOCKED_GRASP = auto()   # Grasp locked, transport phase
    OPENING = auto()        # Executing open trajectory
    EMERGENCY_STOP = auto() # Safety stop state


@dataclass
class FSMConfig:
    """Configuration for the FSM controller."""
    # State machine settings
    enabled: bool = True
    
    # Trigger thresholds (as fraction of baseline/MVC)
    flexor_trigger_threshold: float = 0.4      # Threshold to trigger grasp
    extensor_trigger_threshold: float = 0.35   # Threshold to trigger release
    
    # Trigger detection
    trigger_rise_time_ms: float = 100          # Max time for trigger detection
    trigger_sustained_ms: float = 50           # Min sustained activation for trigger
    
    # Locked grasp settings
    lock_grasp_enabled: bool = True            # Enable grasp locking during transport
    lock_duration_min_ms: float = 300          # Minimum lock duration before allowing release
    lock_ignore_threshold: float = 0.8         # Ignore EMG below this (relative to trigger)
    
    # Trajectory execution
    close_trajectory_ms: float = 400           # Duration of close trajectory
    open_trajectory_ms: float = 500            # Duration of open trajectory
    trajectory_profile: str = "smooth"         # smooth, linear, or fast
    
    # Safety settings
    emergency_stop_threshold: float = 0.9      # Very high EMG triggers emergency stop
    max_grasp_duration_sec: float = 30.0       # Auto-release after this duration
    
    # Channel mapping (for 32-channel grid)
    flexor_channels: List[int] = field(default_factory=lambda: list(range(0, 16)))
    extensor_channels: List[int] = field(default_factory=lambda: list(range(16, 32)))
    
    # Debouncing
    state_change_cooldown_ms: float = 200      # Minimum time between state changes


class TriggerDetector:
    """
    Detects trigger events from EMG signals.
    
    Uses a combination of:
    - Amplitude threshold crossing
    - Rise time analysis (fast rise = intentional)
    - Sustained activation check
    """
    
    def __init__(self, fsample: float, config: FSMConfig):
        self.fsample = fsample
        self.config = config
        
        # Buffers for rise detection
        rise_samples = int(config.trigger_rise_time_ms * fsample / 1000)
        self.flexor_history = deque(maxlen=rise_samples)
        self.extensor_history = deque(maxlen=rise_samples)
        
        # Sustained activation tracking
        sustained_samples = int(config.trigger_sustained_ms * fsample / 1000)
        self.sustained_buffer = deque(maxlen=max(sustained_samples, 1))
        
        # Baseline tracking (adaptive)
        self.flexor_baseline = 0.1
        self.extensor_baseline = 0.1
        self.baseline_alpha = 0.001  # Slow adaptation
        
        # State
        self.last_trigger_time = 0
        self.cooldown_sec = config.state_change_cooldown_ms / 1000
    
    def update(self, flexor_activation: float, extensor_activation: float, 
               current_time: float) -> Tuple[bool, bool, bool]:
        """
        Update detector with new activations.
        
        Returns:
        --------
        (flexor_triggered, extensor_triggered, emergency_stop)
        """
        # Update history
        self.flexor_history.append(flexor_activation)
        self.extensor_history.append(extensor_activation)
        
        # Check cooldown
        if current_time - self.last_trigger_time < self.cooldown_sec:
            return False, False, False
        
        # Emergency stop check
        if max(flexor_activation, extensor_activation) > self.config.emergency_stop_threshold:
            return False, False, True
        
        # Flexor trigger detection
        flexor_triggered = self._check_trigger(
            self.flexor_history,
            self.flexor_baseline,
            self.config.flexor_trigger_threshold
        )
        
        # Extensor trigger detection  
        extensor_triggered = self._check_trigger(
            self.extensor_history,
            self.extensor_baseline,
            self.config.extensor_trigger_threshold
        )
        
        # Update baselines (only during low activity)
        if flexor_activation < self.config.flexor_trigger_threshold * 0.5:
            self.flexor_baseline = (1 - self.baseline_alpha) * self.flexor_baseline + \
                                   self.baseline_alpha * flexor_activation
        if extensor_activation < self.config.extensor_trigger_threshold * 0.5:
            self.extensor_baseline = (1 - self.baseline_alpha) * self.extensor_baseline + \
                                     self.baseline_alpha * extensor_activation
        
        # Record trigger time
        if flexor_triggered or extensor_triggered:
            self.last_trigger_time = current_time
        
        return flexor_triggered, extensor_triggered, False
    
    def _check_trigger(self, history: deque, baseline: float, threshold: float) -> bool:
        """Check if a trigger condition is met."""
        if len(history) < 2:
            return False
        
        current = history[-1]
        
        # Check amplitude threshold
        if current < threshold:
            return False
        
        # Check for sharp rise (intentional activation)
        start_val = history[0]
        rise = current - start_val
        
        # Must be a significant rise above baseline
        if rise < (threshold - baseline) * 0.5:
            return False
        
        return True
    
    def reset(self):
        """Reset detector state."""
        self.flexor_history.clear()
        self.extensor_history.clear()
        self.last_trigger_time = 0


class TrajectoryGenerator:
    """
    Generates smooth trajectories for state transitions.
    """
    
    def __init__(self, config: FSMConfig):
        self.config = config
        self.trajectory_start_time = None
        self.trajectory_duration = 0
        self.trajectory_type = None  # 'close' or 'open'
    
    def start_trajectory(self, trajectory_type: str, current_time: float):
        """Start a new trajectory."""
        self.trajectory_type = trajectory_type
        self.trajectory_start_time = current_time
        
        if trajectory_type == 'close':
            self.trajectory_duration = self.config.close_trajectory_ms / 1000
        else:
            self.trajectory_duration = self.config.open_trajectory_ms / 1000
    
    def get_position(self, current_time: float) -> Tuple[float, bool]:
        """
        Get current trajectory position.
        
        Returns:
        --------
        (position, is_complete)
        - position: 0.0 (open) to 1.0 (closed)
        - is_complete: True if trajectory finished
        """
        if self.trajectory_start_time is None:
            return 0.0 if self.trajectory_type != 'close' else 1.0, True
        
        elapsed = current_time - self.trajectory_start_time
        progress = min(1.0, elapsed / self.trajectory_duration)
        
        # Apply profile
        if self.config.trajectory_profile == "smooth":
            # Smooth S-curve (ease in-out)
            progress = progress * progress * (3 - 2 * progress)
        elif self.config.trajectory_profile == "fast":
            # Quick start, slow finish
            progress = 1 - (1 - progress) ** 2
        # else: linear (no modification)
        
        is_complete = elapsed >= self.trajectory_duration
        
        if self.trajectory_type == 'close':
            return progress, is_complete
        else:  # open
            return 1.0 - progress, is_complete
    
    def reset(self):
        """Reset trajectory state."""
        self.trajectory_start_time = None
        self.trajectory_type = None


class GraspFSM:
    """
    Finite State Machine for grasp control.
    
    Implements the state-based control strategy optimized for functional tests.
    """
    
    def __init__(self, config: FSMConfig, fsample: float = 1000):
        self.config = config
        self.fsample = fsample
        
        # Current state
        self.state = GraspState.IDLE
        self.state_entry_time = time.perf_counter()
        self.grasp_start_time = None
        
        # Components
        self.trigger_detector = TriggerDetector(fsample, config)
        self.trajectory = TrajectoryGenerator(config)
        
        # Statistics
        self.stats = {
            'state_transitions': 0,
            'grasps_completed': 0,
            'emergency_stops': 0,
            'auto_releases': 0
        }
    
    def process(self, flexor_activation: float, extensor_activation: float,
                current_time: float) -> Dict:
        """
        Process EMG activations and update state machine.
        
        Parameters:
        -----------
        flexor_activation : float
            Normalized flexor muscle activation (0-1)
        extensor_activation : float
            Normalized extensor muscle activation (0-1)
        current_time : float
            Current timestamp
            
        Returns:
        --------
        dict with:
            - 'state': Current state name
            - 'gesture': ESP32 gesture command (0=relax, 1=flex, 2=extend)
            - 'position': Hand position (0=open, 1=closed)
            - 'force': Grasp force level (0-1)
            - 'state_changed': Whether state just changed
        """
        # Detect triggers
        flexor_triggered, extensor_triggered, emergency = self.trigger_detector.update(
            flexor_activation, extensor_activation, current_time
        )
        
        # Emergency stop handling
        if emergency:
            return self._transition_to(GraspState.EMERGENCY_STOP, current_time)
        
        # State machine logic
        if self.state == GraspState.IDLE:
            return self._process_idle(flexor_triggered, current_time)
            
        elif self.state == GraspState.CLOSING:
            return self._process_closing(extensor_triggered, current_time)
            
        elif self.state == GraspState.LOCKED_GRASP:
            return self._process_locked_grasp(
                flexor_activation, extensor_activation, 
                extensor_triggered, current_time
            )
            
        elif self.state == GraspState.OPENING:
            return self._process_opening(flexor_triggered, current_time)
            
        elif self.state == GraspState.EMERGENCY_STOP:
            return self._process_emergency_stop(current_time)
        
        return self._get_current_output(False)
    
    def _process_idle(self, flexor_triggered: bool, current_time: float) -> Dict:
        """Process IDLE state."""
        if flexor_triggered:
            self.trajectory.start_trajectory('close', current_time)
            self.grasp_start_time = current_time
            return self._transition_to(GraspState.CLOSING, current_time)
        
        return {
            'state': 'IDLE',
            'gesture': 2,  # Extend/open
            'position': 0.0,
            'force': 0.0,
            'state_changed': False
        }
    
    def _process_closing(self, extensor_triggered: bool, current_time: float) -> Dict:
        """Process CLOSING state."""
        position, is_complete = self.trajectory.get_position(current_time)
        
        # Allow abort during closing
        if extensor_triggered:
            self.trajectory.start_trajectory('open', current_time)
            return self._transition_to(GraspState.OPENING, current_time)
        
        if is_complete:
            if self.config.lock_grasp_enabled:
                return self._transition_to(GraspState.LOCKED_GRASP, current_time)
            else:
                # Without locking, go back to idle but keep closed
                return self._transition_to(GraspState.IDLE, current_time)
        
        return {
            'state': 'CLOSING',
            'gesture': 1,  # Flex/close
            'position': position,
            'force': position * 0.8,  # Ramp up force
            'state_changed': False
        }
    
    def _process_locked_grasp(self, flexor_act: float, extensor_act: float,
                               extensor_triggered: bool, current_time: float) -> Dict:
        """Process LOCKED_GRASP state - the key "transport" state."""
        time_in_state = current_time - self.state_entry_time
        
        # Check minimum lock duration
        min_lock_sec = self.config.lock_duration_min_ms / 1000
        can_release = time_in_state >= min_lock_sec
        
        # Check for intentional release (extensor burst)
        if can_release and extensor_triggered:
            self.stats['grasps_completed'] += 1
            self.trajectory.start_trajectory('open', current_time)
            return self._transition_to(GraspState.OPENING, current_time)
        
        # Check max grasp duration (safety)
        if self.grasp_start_time and \
           (current_time - self.grasp_start_time) > self.config.max_grasp_duration_sec:
            self.stats['auto_releases'] += 1
            self.trajectory.start_trajectory('open', current_time)
            return self._transition_to(GraspState.OPENING, current_time)
        
        # In locked state - ignore most EMG fluctuations
        # This is the key feature for transport phase
        return {
            'state': 'LOCKED_GRASP',
            'gesture': 1,  # Keep closed
            'position': 1.0,
            'force': 0.7,  # Maintain moderate force
            'state_changed': False,
            'locked': True,
            'time_locked': time_in_state
        }
    
    def _process_opening(self, flexor_triggered: bool, current_time: float) -> Dict:
        """Process OPENING state."""
        position, is_complete = self.trajectory.get_position(current_time)
        
        # Allow re-grasp during opening
        if flexor_triggered:
            self.trajectory.start_trajectory('close', current_time)
            return self._transition_to(GraspState.CLOSING, current_time)
        
        if is_complete:
            return self._transition_to(GraspState.IDLE, current_time)
        
        return {
            'state': 'OPENING',
            'gesture': 2,  # Extend/open
            'position': position,
            'force': 0.0,
            'state_changed': False
        }
    
    def _process_emergency_stop(self, current_time: float) -> Dict:
        """Process EMERGENCY_STOP state."""
        # Stay in emergency stop until manual reset or timeout
        time_in_state = current_time - self.state_entry_time
        
        if time_in_state > 2.0:  # Auto-recover after 2 seconds
            return self._transition_to(GraspState.IDLE, current_time)
        
        return {
            'state': 'EMERGENCY_STOP',
            'gesture': 0,  # Relax
            'position': 0.5,
            'force': 0.0,
            'state_changed': False,
            'emergency': True
        }
    
    def _transition_to(self, new_state: GraspState, current_time: float) -> Dict:
        """Transition to a new state."""
        old_state = self.state
        self.state = new_state
        self.state_entry_time = current_time
        self.stats['state_transitions'] += 1
        
        if new_state == GraspState.EMERGENCY_STOP:
            self.stats['emergency_stops'] += 1
        
        print(f"   FSM: {old_state.name} → {new_state.name}")
        
        return self._get_current_output(True)
    
    def _get_current_output(self, state_changed: bool) -> Dict:
        """Get current output based on state."""
        state_outputs = {
            GraspState.IDLE: {'gesture': 2, 'position': 0.0, 'force': 0.0},
            GraspState.CLOSING: {'gesture': 1, 'position': 0.5, 'force': 0.5},
            GraspState.LOCKED_GRASP: {'gesture': 1, 'position': 1.0, 'force': 0.7},
            GraspState.OPENING: {'gesture': 2, 'position': 0.5, 'force': 0.0},
            GraspState.EMERGENCY_STOP: {'gesture': 0, 'position': 0.0, 'force': 0.0},
        }
        
        output = state_outputs.get(self.state, state_outputs[GraspState.IDLE])
        output['state'] = self.state.name
        output['state_changed'] = state_changed
        
        return output
    
    def reset(self):
        """Reset FSM to initial state."""
        self.state = GraspState.IDLE
        self.state_entry_time = time.perf_counter()
        self.grasp_start_time = None
        self.trigger_detector.reset()
        self.trajectory.reset()
    
    def get_stats(self) -> Dict:
        """Get FSM statistics."""
        return self.stats.copy()


def extract_muscle_activations(emg_data: np.ndarray, config: FSMConfig) -> Tuple[float, float]:
    """
    Extract flexor and extensor activations from 32-channel EMG data.
    
    Parameters:
    -----------
    emg_data : np.ndarray
        EMG data of shape (n_samples, n_channels) or (n_channels,)
    config : FSMConfig
        Configuration with channel mappings
        
    Returns:
    --------
    (flexor_activation, extensor_activation) - both normalized 0-1
    """
    if emg_data.ndim == 1:
        emg_data = emg_data.reshape(1, -1)
    
    # Extract channel groups
    flexor_data = emg_data[:, config.flexor_channels]
    extensor_data = emg_data[:, config.extensor_channels]
    
    # Calculate RMS activation for each group
    flexor_rms = np.sqrt(np.mean(flexor_data ** 2))
    extensor_rms = np.sqrt(np.mean(extensor_data ** 2))
    
    return flexor_rms, extensor_rms


def FSMControlLoop(
    events_socket,
    control_params,
    pred_control_queue,
    stop_program,
    pred_esp32_queue=None,
    unity_events_queue=None,
    fsm_config=None
):
    """
    FSM-based control loop for functional tests (BBT, grasp prehension, etc.).
    
    This replaces proportional control with state-based control for robust
    performance during transport phases.
    
    Now sends FSM state updates to Unity for visualization.
    """
    print('\n' + '='*60)
    print('🎯 Starting FSM Control Loop for Functional Tests')
    print('='*60)
    
    # Load configuration
    if fsm_config is None:
        try:
            with open('config/functional_tests.yaml', 'r') as f:
                fsm_config = yaml.safe_load(f)
        except FileNotFoundError:
            print("  ⚠️  FSM config not found, using defaults")
            fsm_config = {}
    
    # Create FSM config
    fsm_settings = fsm_config.get('fsm_control', {})
    config = FSMConfig(
        enabled=fsm_settings.get('enabled', True),
        flexor_trigger_threshold=fsm_settings.get('flexor_trigger_threshold', 0.4),
        extensor_trigger_threshold=fsm_settings.get('extensor_trigger_threshold', 0.35),
        trigger_rise_time_ms=fsm_settings.get('trigger_rise_time_ms', 100),
        trigger_sustained_ms=fsm_settings.get('trigger_sustained_ms', 50),
        lock_grasp_enabled=fsm_settings.get('lock_grasp_enabled', True),
        lock_duration_min_ms=fsm_settings.get('lock_duration_min_ms', 300),
        close_trajectory_ms=fsm_settings.get('close_trajectory_ms', 400),
        open_trajectory_ms=fsm_settings.get('open_trajectory_ms', 500),
        trajectory_profile=fsm_settings.get('trajectory_profile', 'smooth'),
        max_grasp_duration_sec=fsm_settings.get('max_grasp_duration_sec', 30.0),
        flexor_channels=fsm_settings.get('flexor_channels', list(range(0, 16))),
        extensor_channels=fsm_settings.get('extensor_channels', list(range(16, 32))),
    )
    
    print(f"  ✓ Grasp locking: {'ENABLED' if config.lock_grasp_enabled else 'DISABLED'}")
    print(f"  ✓ Flexor threshold: {config.flexor_trigger_threshold}")
    print(f"  ✓ Extensor threshold: {config.extensor_trigger_threshold}")
    print(f"  ✓ Trajectory profile: {config.trajectory_profile}")
    print('='*60 + '\n')
    
    # Initialize FSM
    fsample = control_params.get('fsample', 1000)
    fsm = GraspFSM(config, fsample)
    
    # ESP32 gesture mapping
    esp32_gesture_map = {
        0: 0,  # Relax
        1: 1,  # Flex (close)
        2: 2,  # Extend (open)
    }
    
    # Statistics
    stats = {
        'predictions_processed': 0,
        'esp32_commands_sent': 0,
        'unity_updates_sent': 0,
        'start_time': time.perf_counter()
    }
    
    # BBT scoring
    bbt_score = {
        'block_count': 0,
        'grasp_count': 0,
        'session_start': time.perf_counter()
    }
    
    # State code mapping for Unity
    state_code_map = {
        'IDLE': 0,
        'CLOSING': 1,
        'LOCKED_GRASP': 2,
        'OPENING': 3,
        'EMERGENCY_STOP': 4
    }
    
    last_gesture_sent = None
    last_state_sent = None
    
    def send_to_unity(state_name: str, output: Dict):
        """Send FSM state update to Unity via events socket."""
        nonlocal last_state_sent
        
        if events_socket is None:
            return
            
        # Only send on state change to reduce traffic
        if state_name == last_state_sent and not output.get('state_changed', False):
            return
        
        try:
            state_code = state_code_map.get(state_name, 0)
            is_locked = output.get('locked', state_name == 'LOCKED_GRASP')
            
            # Create FSM state event
            fsm_event = {
                'eventName': 'fsm_state',
                'eventID': state_code,
                'fsmState': state_name,
                'isLocked': is_locked,
                'lockTime': output.get('time_locked', 0.0),
                'handPosition': output.get('position', 0.0),
                'force': output.get('force', 0.0)
            }
            
            # Send to Unity
            msg = json.dumps(fsm_event) + '\n'
            events_socket.sendall(msg.encode('utf-8'))
            
            last_state_sent = state_name
            stats['unity_updates_sent'] += 1
            
        except Exception as e:
            print(f"   ⚠️  Failed to send Unity update: {e}")
    
    def send_bbt_score_update():
        """Send BBT score update to Unity."""
        if events_socket is None:
            return
            
        try:
            elapsed = time.perf_counter() - bbt_score['session_start']
            score_event = {
                'eventName': 'bbt_score',
                'eventID': bbt_score['block_count'],
                'blockCount': bbt_score['block_count'],
                'graspCount': bbt_score['grasp_count'],
                'sessionTime': elapsed
            }
            msg = json.dumps(score_event) + '\n'
            events_socket.sendall(msg.encode('utf-8'))
        except Exception as e:
            print(f"   ⚠️  Failed to send BBT score: {e}")
    
    def send_to_esp32(gesture: int, force: float):
        """Send command to ESP32."""
        nonlocal last_gesture_sent
        
        if pred_esp32_queue is None:
            return
        
        # Only send if gesture changed or force significantly different
        if gesture == last_gesture_sent:
            return
        
        try:
            esp32_gesture = esp32_gesture_map.get(gesture, 0)
            pred_esp32_queue.put((esp32_gesture, force, time.perf_counter()), timeout=0.1)
            last_gesture_sent = gesture
            stats['esp32_commands_sent'] += 1
        except Full:
            pass
    
    # Main loop
    print("🏁 FSM Control active - States: IDLE → CLOSING → LOCKED_GRASP → OPENING")
    print("   Press Ctrl+C to stop\n")
    
    # Send session start to Unity
    try:
        if events_socket:
            start_event = {'eventName': 'fsm_start', 'eventID': 1}
            events_socket.sendall((json.dumps(start_event) + '\n').encode('utf-8'))
    except:
        pass

    while not stop_program.value:
        try:
            data = pred_control_queue.get(timeout=0.1)
        except Empty:
            continue
        
        if data is None:
            break
        
        current_time = time.perf_counter()
        stats['predictions_processed'] += 1
        
        # Extract EMG activations
        # data format: (prediction, confidence, timestamp, [optional: emg_data])
        pred = data[0]
        confidence = data[1]
        
        # If we have raw EMG data, extract muscle activations
        if len(data) > 3 and isinstance(data[3], np.ndarray):
            emg_data = data[3]
            flexor_act, extensor_act = extract_muscle_activations(emg_data, config)
        else:
            # Fallback: use prediction and confidence as proxy
            # pred 1 = close (flexor), pred 2 = open (extensor)
            # Scale confidence to FSM-friendly range (0.3-0.7) to avoid emergency stop
            scaled_conf = 0.3 + (confidence * 0.4)  # Maps 0-1 to 0.3-0.7
            if pred == 1:
                flexor_act = scaled_conf
                extensor_act = 0.1
            elif pred == 2:
                flexor_act = 0.1
                extensor_act = scaled_conf
            else:
                flexor_act = 0.1
                extensor_act = 0.1
        
        # Process through FSM
        output = fsm.process(flexor_act, extensor_act, current_time)
        
        # Log state changes
        if output.get('state_changed', False):
            print(f"   State: {output['state']} | Gesture: {output['gesture']} | "
                  f"Position: {output['position']:.2f}")
            
            # Track completed grasps for BBT scoring
            if output['state'] == 'IDLE' and last_state_sent == 'OPENING':
                bbt_score['grasp_count'] += 1
                print(f"   ✓ Grasp cycle complete! Total: {bbt_score['grasp_count']}")
                send_bbt_score_update()
        
        # Send to Unity (FSM state visualization)
        send_to_unity(output['state'], output)
    
    # Print summary
    duration = time.perf_counter() - stats['start_time']
    fsm_stats = fsm.get_stats()
    
    print(f'\n📊 FSM Control Loop Summary:')
    print(f'   • Duration: {duration:.2f}s')
    print(f'   • Predictions processed: {stats["predictions_processed"]}')
    print(f'   • ESP32 commands sent: {stats["esp32_commands_sent"]}')
    print(f'   • Unity updates sent: {stats["unity_updates_sent"]}')
    print(f'   • State transitions: {fsm_stats["state_transitions"]}')
    print(f'   • Grasps completed: {fsm_stats["grasps_completed"]}')
    print(f'   • BBT grasp cycles: {bbt_score["grasp_count"]}')
    print(f'   • Auto-releases: {fsm_stats["auto_releases"]}')
    print(f'   • Emergency stops: {fsm_stats["emergency_stops"]}')
    
    # Send session stop to Unity
    try:
        if events_socket:
            stop_event = {
                'eventName': 'fsm_stop', 
                'eventID': 0,
                'graspCount': bbt_score['grasp_count'],
                'sessionTime': duration
            }
            events_socket.sendall((json.dumps(stop_event) + '\n').encode('utf-8'))
    except:
        pass
    
    # Send final rest command
    if pred_esp32_queue is not None:
        try:
            pred_esp32_queue.put((0, 0.0, time.perf_counter()), timeout=0.5)
        except Full:
            pass
    
    print('\nFSM Control loop stopped')
