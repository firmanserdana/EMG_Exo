from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable, List, Sequence

import cv2
import easyocr
import numpy as np

# --- CONFIGURATION ---
IMAGE_ROOT = Path(__file__).parent
SUBFOLDER_GLOB = "s*"
SCREENSHOTS_PER_SESSION = 2
SESSION_FILE_TEMPLATE = "session_{:02d}.npy"
GPU_ENABLED = False
ALLOWED_EXTENSIONS = (".png", ".jpg", ".jpeg", ".PNG", ".JPG", ".JPEG")
# --- END CONFIGURATION ---

# Regex to find timestamps. Handles "1:23,45" or "01:23.45"
RE_TIMESTAMP = re.compile(r"(\d{1,2}:\d{2}[,.]\d{2})")


def natural_key(path: Path) -> List[object]:
    parts: List[object] = []
    for token in re.split(r"(\d+)", path.name):
        if token.isdigit():
            parts.append(int(token))
        elif token:
            parts.append(token.lower())
    return parts


def standardize_time(time_str: str) -> str:
    time_str = time_str.replace(",", ".")
    if ":" in time_str and time_str.find(":") < 2:
        time_str = "0" + time_str
    return time_str


def time_str_to_seconds(time_str: str) -> float:
    minutes, seconds = time_str.split(":")
    return int(minutes) * 60 + float(seconds)


def robust_cv_read(image_path: Path) -> np.ndarray | None:
    try:
        data = np.fromfile(str(image_path), np.uint8)
        image = cv2.imdecode(data, cv2.IMREAD_COLOR)
        if image is None:
            print(f"  Warning: cv2.imdecode returned None for {image_path.name}")
        return image
    except Exception as exc:  # pragma: no cover - defensive guard
        print(f"  Error reading {image_path.name}: {exc}")
        return None


def preprocess_for_ocr(image: np.ndarray) -> np.ndarray | None:
    if image is None or image.size == 0:
        return None
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    _, binarized = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY_INV)
    return binarized


def extract_timestamps_from_image(reader: easyocr.Reader, image_path: Path) -> List[str]:
    image = robust_cv_read(image_path)
    processed = preprocess_for_ocr(image)
    if processed is None:
        return []

    results = reader.readtext(processed, detail=1, paragraph=False)
    results_sorted = sorted(
        results,
        key=lambda r: (min(pt[1] for pt in r[0]), min(pt[0] for pt in r[0])),
    )

    hits: List[str] = []
    for _, text, _ in results_sorted:
        for match in RE_TIMESTAMP.finditer(text):
            hits.append(standardize_time(match.group(1)))

    if not hits:
        print(f"    Warning: No timestamps detected in {image_path.name}")
    return hits


def iter_image_files(folder: Path) -> List[Path]:
    images = [p for p in folder.iterdir() if p.suffix in ALLOWED_EXTENSIONS]
    return sorted(images, key=natural_key)


def chunk(sequence: Sequence[Path], size: int) -> Iterable[List[Path]]:
    for start in range(0, len(sequence), size):
        yield list(sequence[start:start + size])


def build_session_payload(times: List[str], session_idx: int) -> dict | None:
    if not times:
        return None

    # Convert all detected times to seconds
    seconds = [time_str_to_seconds(t) for t in times]
    if not seconds:
        return None

    # Sort to enforce chronological order
    seconds = sorted(seconds)

    # Heuristic: if the first detected time is already large (e.g., 29s), treat
    # values as absolute elapsed times and normalize to start at zero. Otherwise
    # treat values as lap durations and convert to cumulative boundaries.
    seconds_list: List[float] = []
    if seconds and seconds[0] > 10.0:
        base = seconds[0]
        seconds_list = [s - base for s in seconds]
    else:
        running_total = 0.0
        for duration in seconds:
            running_total += duration
            seconds_list.append(running_total)

    created_at = datetime.now()
    session_start = created_at - timedelta(seconds=max(seconds_list) + 1.0)

    gestures = [
        {
            "gesture_id": i + 1,
            "timestamp": seconds,
            "absolute_time": (session_start + timedelta(seconds=seconds)).isoformat(),
            "description": f"Gesture {i + 1}",
        }
        for i, seconds in enumerate(seconds_list)
    ]

    return {
        "session_info": {
            "total_gestures": len(gestures),
            "session_file": SESSION_FILE_TEMPLATE.format(session_idx),
            "created_at": created_at.isoformat(),
        },
        "gestures": gestures,
    }


def process_folder(folder: Path, reader: easyocr.Reader) -> None:
    image_files = iter_image_files(folder)
    if not image_files:
        print(f"No screenshots found in {folder.name}, skipping.")
        return

    if len(image_files) % SCREENSHOTS_PER_SESSION != 0:
        print(
            f"  Warning: {folder.name} contains {len(image_files)} images, which is not a multiple of {SCREENSHOTS_PER_SESSION}. Extra images will be ignored."
        )

    for session_idx, image_group in enumerate(chunk(image_files, SCREENSHOTS_PER_SESSION), start=1):
        if len(image_group) < SCREENSHOTS_PER_SESSION:
            print(f"  Skipping incomplete session {session_idx} in {folder.name}.")
            continue

        print(f"Processing {folder.name} session {session_idx} using {[p.name for p in image_group]}")

        all_times: List[str] = []
        for image_path in image_group:
            all_times.extend(extract_timestamps_from_image(reader, image_path))

        payload = build_session_payload(all_times, session_idx)
        if payload is None:
            print(f"  No timestamps found for session {session_idx} in {folder.name}, skipping output.")
            continue

        output_path = folder / f"session_{session_idx:02d}_timestamps.json"
        output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"  Wrote {output_path.name} with {len(payload['gestures'])} gesture(s).")


def main():
    folders = [p for p in IMAGE_ROOT.glob(SUBFOLDER_GLOB) if p.is_dir()]
    folders = sorted(folders, key=natural_key)

    if not folders:
        print(f"No folders matching '{SUBFOLDER_GLOB}' found under {IMAGE_ROOT}.")
        return

    print("Initializing EasyOCR reader...")
    reader = easyocr.Reader(["en"], gpu=GPU_ENABLED)
    print("EasyOCR ready. Starting extraction.")

    for folder in folders:
        print(f"\n=== {folder.name} ===")
        process_folder(folder, reader)

    print("\n--- Extraction Complete ---")


if __name__ == "__main__":
    main()

