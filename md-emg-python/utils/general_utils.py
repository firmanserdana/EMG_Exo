import argparse

def decoding_arg_parser(description=None):
    """Parse command line arguments."""
    if description is None:
        description = 'Arguments for the md-emg decoding experiment scripts.'
        
    parser = argparse.ArgumentParser(description)

    parser.add_argument('--subj_type', type=str, default='SCI',
                        choices=['healthy', 'SCI'],
                        help='Subject type (default: SCI)')
    
    parser.add_argument('--subj', type=int, default=0,
                        help='Subject number (default: 0)')
    
    parser.add_argument('--task', type=str, default='open_close',
                        choices=['open_close', 'grasp_patterns', 'single_fingers'],
                        help='Task type (default: open_close)')
    
    parser.add_argument('--acquisition_type', type=str, default='open_loop',
                        choices=['open_loop', 'closed_loop', 'both'],
                        help='Acquisition type (default: open_loop)')

    parser.add_argument('--session', type=int, default=0,
                        help='Session ID (default: 0)')
    
    parser.add_argument('--load_existing_model', type=int, default=0,
                        help='Session ID (default: 0)')

    return parser.parse_args()

def acquisition_arg_parser(description=None):
    """Parse command line arguments for acquisition scripts."""
    if description is None:
        description = 'Arguments for the md-emg acquisition scripts.'
        
    parser = argparse.ArgumentParser(description)

    parser.add_argument('--subj_type', type=str, default='SCI',
                        choices=['healthy', 'SCI'],
                        help='Subject type (default: SCI)')
    
    parser.add_argument('--subj', type=int, default=0,
                        help='Subject number (default: 0)')
    
    parser.add_argument('--task', type=str, default='open_close',
                        choices=['open_close', 'grasp_patterns', 'single_fingers'],
                        help='Task type (default: open_close)')

    parser.add_argument('--decoding_active', type=int, default=0,
                        help='Decoding active flag (default: 0)')
    
    parser.add_argument('--acquisition_type', type=str, default='open_loop',
                        choices=['open_loop', 'closed_loop', 'both'],
                        help='Acquisition type (default: open_loop)')
    
    parser.add_argument('--session', type=int, default=0,
                        help='Session ID (default: 0)')

    parser.add_argument('--is_mvc_session', type=int, default=0,
                        help='Is Maximum Voluntary Contraction (MVC) session flag (default: 0)')

    parser.add_argument('--esp32_enabled', type=int, default=None,
                        help='Enable ESP32 glove control (0/1). If not specified, uses config file setting.')

    parser.add_argument('--control_mode', type=str, default='synchronized',
                        choices=['unity_only', 'esp32_only', 'synchronized'],
                        help='Control mode: unity_only (ESP32 independent), esp32_only (no Unity events), synchronized (ESP32 follows Unity) (default: synchronized)')

    return parser.parse_args()