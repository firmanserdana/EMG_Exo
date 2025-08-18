import sys
import os
import argparse

# Add the project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils.data_utils import *


def parse_args():
    parser = argparse.ArgumentParser(
        description="Load saved event pickles and export to CSV for quick inspection"
    )
    parser.add_argument(
        "--subj-type",
        choices=["healthy", "SCI"],
        default="healthy",
        help="Subject cohort folder",
    )
    parser.add_argument(
        "--subj",
        type=int,
        default=0,
        help="Subject index (e.g., 0 => S0)",
    )
    parser.add_argument(
        "--session",
        type=int,
        default=None,
        help="Session number to load; omit to load all sessions",
    )
    parser.add_argument(
        "--out",
        type=str,
        default=None,
        help="Optional output CSV path or directory. If a directory, one CSV per events file will be written.",
    )
    parser.add_argument(
        "--no-pause",
        action="store_true",
        help="Do not pause after printing preview",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    subj_type = args.subj_type
    subj = args.subj
    session = args.session
    subj_id = f"S{subj}"

    # folders definition
    root_folder = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    data_folder_src = os.path.join(
        root_folder, "data", subj_type, subj_id, "raw"
    )  # source folder for the data

    if not os.path.isdir(data_folder_src):
        raise FileNotFoundError(f"Data folder not found: {data_folder_src}")

    # Determine which files to load
    event_files = []
    if session is not None:
        candidate = os.path.join(
            data_folder_src, f"session_{session:02d}_events.pkl"
        )
        if not os.path.isfile(candidate):
            raise FileNotFoundError(f"Events file not found: {candidate}")
        event_files = [candidate]
    else:
        event_files = [
            os.path.join(data_folder_src, f)
            for f in os.listdir(data_folder_src)
            if f.endswith("_events.pkl")
        ]
        event_files.sort()

    # Prepare output path(s)
    default_out_dir = os.path.join(root_folder, "debug")
    if args.out:
        # If --out given and it's an existing directory, use it. If it ends with .csv, treat as file path.
        if args.out.endswith(".csv"):
            out_dir = os.path.dirname(args.out) or default_out_dir
            out_file_fixed = os.path.basename(args.out)
            os.makedirs(out_dir, exist_ok=True)
        else:
            out_dir = args.out
            out_file_fixed = None
            os.makedirs(out_dir, exist_ok=True)
    else:
        out_dir = default_out_dir
        out_file_fixed = None
        os.makedirs(out_dir, exist_ok=True)

    for event_file_path in event_files:
        if session is not None:
            print(f"Loading events subject {subj_id} from session {session}")
        else:
            print(f"Loading events subject {subj_id} from file {event_file_path}")

        events = load_pickle(event_file_path)
        events_df = create_events_df(events, time_start=0)

        if not events_df.empty:
            time_start = events_df["time"].min()
            events_df["time"] -= time_start

        # save the events_df to a CSV file
        if out_file_fixed and len(event_files) == 1:
            out_csv = os.path.join(out_dir, out_file_fixed)
        else:
            base = os.path.splitext(os.path.basename(event_file_path))[0]
            out_csv = os.path.join(out_dir, f"{base}.csv")

        events_df.to_csv(out_csv, index=False)
        print(f"Saved CSV: {out_csv}")

        print(events_df[:20])

        if not args.no_pause:
            try:
                input("Press Enter to continue")
            except KeyboardInterrupt:
                break


if __name__ == "__main__":
    main()