import sys
import os

# Add the project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils.data_utils import *

# General params
subj_type = 'SCI' # 'healthy' or 'SCI'
subj = 4
session = None # session number to load - None if load all sessions

subj_id = f'S{subj}'

# folders definition
root_folder = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
data_folder_src = os.path.join(root_folder, 'data', subj_type, subj_id, 'raw') # source folder for the data

event_files = [
    os.path.join(data_folder_src, f)
    for f in os.listdir(data_folder_src)
    if f.endswith('_events.pkl')
]

for event_file_path in event_files:
    if session is not None:
        event_file_path = os.path.join(data_folder_src, f'session_{session:02d}_events.pkl')

        print(f"Loading events subject {subj_id} from session {session}")
    else:
        print(f"Loading events subject {subj_id} from file {event_file_path}")
    
    events = load_pickle(event_file_path)
    events_df = create_events_df(events, time_start=0)

    time_start = events_df['time'].min()

    events_df['time'] -= time_start

    # save the events_df to a CSV file
    events_df.to_csv('debug/debug_events.csv', index=False)

    print(events_df[:20])

    # wait enter to continue
    input("Press Enter to continue")