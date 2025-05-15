# EMG-Controlled 3D Hand in Unity

This directory contains Unity scripts and assets for the 3D hand visualization and control system, which receives EMG signals from the Python backend.

## Features

- 3D hand model with 12 degrees of freedom (DoF):
  - Thumb, index, and middle fingers have 3 DoF each (flexion, extension, and pinching)
  - Ring and little fingers share 2 DoF (flexion and extension)
  - Thumb abduction as an additional DoF
- Real-time EMG signal visualization
- Support for UDP and TCP communication
- Smooth interpolation for natural hand movements

## Setting Up the Unity Scene

### Option 1: Using the EMG Scene Setup Tool

1. Open an empty Unity scene
2. Go to the menu: EMG Tools > Setup EMG Scene
3. This will automatically set up the scene with:
   - A 3D hand model (if the prefab is assigned)
   - Communication handler
   - UI visualizer
   - Camera and lighting

### Option 2: Manual Setup

1. Add the following components to your scene:
   - Create an empty GameObject and add the `EMGCommunicationHandler` script
   - Import a hand model or create one with appropriate bone hierarchy
   - Add the `EMGHandController` script to the hand model GameObject
   - Set up the finger bones in the inspector, or use auto-assignment
   - Optionally, add the `EMGVisualizer` script to a UI canvas

## Configuring Network Communication

By default, the system uses UDP on port 9000. You can configure these settings in the Inspector:

1. Select the GameObject with the `EMGCommunicationHandler` script
2. Set the appropriate IP address (default: 127.0.0.1 for local communication)
3. Set the port number (default: 9000)
4. Choose between UDP and TCP communication

## Hand Model Requirements

For the system to work with a custom hand model, the model should have:

1. A hierarchical bone structure for each finger
2. Each finger should have at least 3 bones (metacarpal, proximal, and distal)
3. The `EMGHandController` script will need references to these bones

## Testing the Implementation

1. Run the Unity scene
2. Use the Python EMG processing application to send commands
3. Alternatively, use the test sequence in the Python application:
   ```python
   python unity_hand_interface.py
   ```
   This will send a sequence of predefined gestures to test the system.

## Troubleshooting

- If the hand doesn't respond, check the communication settings in both Unity and Python.
- Verify that firewalls aren't blocking the UDP/TCP communication.
- Check the console for any error messages from the communication handler.
- Ensure that the bone references in the `EMGHandController` are set correctly.

## Implementation Notes

The system is designed to be modular and extensible. The main components are:

- **Communication**: Handled by `EMGCommunicationHandler`
- **Hand Control**: Implemented in `EMGHandController`
- **Visualization**: Provided by `EMGVisualizer`
- **Scene Setup**: Tool available in `EMGSceneSetup`

Each component can be modified or replaced independently to suit different needs.