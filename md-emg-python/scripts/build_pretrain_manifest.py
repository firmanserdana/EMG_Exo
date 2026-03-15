#!/usr/bin/env python3
"""Build healthy pretraining manifest for S1-S10 with hybrid fallback.

Hybrid policy:
1. Use mapped sessions from SESSION_MAPPINGS_CLEAN first.
2. If mapped session files are missing, log exclusion reason.
3. Add discovered valid sessions (npy + timestamps json) not in mapping.

Usage:
  python scripts/build_pretrain_manifest.py \
      --subjects S1,S2,S3,S4,S5,S6,S7,S8,S9,S10 \
      --output manifests/healthy_pretrain_manifest.json
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Set


SESSION_MAPPINGS_CLEAN = {
    "S1": {"no_glove": [1, 2, 3], "passive_glove": [4, 5, 6], "active_glove": [7, 8, 9]},
    "S2": {"no_glove": [4, 5, 6], "passive_glove": [1, 2, 3], "active_glove": [7, 8, 9]},
    "S3": {"no_glove": [4, 5, 6], "passive_glove": [7, 8, 9], "active_glove": [1, 2, 3]},
    "S4": {"no_glove": [1, 2, 3], "passive_glove": [7, 8, 9], "active_glove": [4, 5, 6]},
    "S5": {"no_glove": [7, 8, 9], "passive_glove": [4, 5, 6], "active_glove": [1, 2, 3]},
    "S6": {"no_glove": [7, 8, 9], "passive_glove": [1, 2, 3], "active_glove": [4, 5, 6]},
    "S7": {"no_glove": [5, 6], "passive_glove": [9, 10], "active_glove": [11, 12, 13]},
    "S8": {"no_glove": [4, 6, 7], "passive_glove": [1, 2, 3], "active_glove": [8, 9, 10]},
    "S9": {"no_glove": [5, 6, 7], "passive_glove": [2, 3, 4], "active_glove": [10, 13]},
    "S10": {"no_glove": [1, 2, 3], "passive_glove": [8, 9, 10], "active_glove": [5, 7]},
}


SESSION_PATTERN = re.compile(r"session_(\d{2})\.npy$")


@dataclass
class ManifestEntry:
    subject: str
    condition: str
    session: int
    source: str  # mapped | fallback
    npy_path: str
    timestamps_path: str


@dataclass
class ExcludedEntry:
    subject: str
    condition: str
    session: int
    reason: str


def parse_subjects(subjects_arg: str) -> List[str]:
    return [s.strip() for s in subjects_arg.split(",") if s.strip()]


def discover_valid_sessions(emg_logs_dir: Path) -> Set[int]:
    valid: Set[int] = set()
    if not emg_logs_dir.exists():
        return valid

    for npy_file in emg_logs_dir.glob("session_*.npy"):
        match = SESSION_PATTERN.search(npy_file.name)
        if not match:
            continue
        sess = int(match.group(1))
        ts_file = emg_logs_dir / f"session_{sess:02d}_timestamps.json"
        if ts_file.exists():
            valid.add(sess)
    return valid


def build_manifest(data_root: Path, subjects: List[str]) -> Dict:
    entries: List[ManifestEntry] = []
    excluded: List[ExcludedEntry] = []

    for subject in subjects:
        emg_logs_dir = data_root / subject / "emg_logs"
        if not emg_logs_dir.exists():
            excluded.append(ExcludedEntry(subject, "all", -1, f"missing directory: {emg_logs_dir}"))
            continue

        mapped = SESSION_MAPPINGS_CLEAN.get(subject, {})
        mapped_sessions: Set[int] = set()

        # 1) mapped sessions first
        for condition, sessions in mapped.items():
            for sess in sessions:
                mapped_sessions.add(sess)
                npy_file = emg_logs_dir / f"session_{sess:02d}.npy"
                ts_file = emg_logs_dir / f"session_{sess:02d}_timestamps.json"
                if npy_file.exists() and ts_file.exists():
                    entries.append(
                        ManifestEntry(
                            subject=subject,
                            condition=condition,
                            session=sess,
                            source="mapped",
                            npy_path=str(npy_file),
                            timestamps_path=str(ts_file),
                        )
                    )
                else:
                    missing_parts = []
                    if not npy_file.exists():
                        missing_parts.append("npy")
                    if not ts_file.exists():
                        missing_parts.append("timestamps")
                    excluded.append(
                        ExcludedEntry(
                            subject=subject,
                            condition=condition,
                            session=sess,
                            reason=f"mapped missing {','.join(missing_parts)}",
                        )
                    )

        # 2) fallback discovery
        discovered = discover_valid_sessions(emg_logs_dir)
        fallback_sessions = sorted(s for s in discovered if s not in mapped_sessions)
        for sess in fallback_sessions:
            npy_file = emg_logs_dir / f"session_{sess:02d}.npy"
            ts_file = emg_logs_dir / f"session_{sess:02d}_timestamps.json"
            entries.append(
                ManifestEntry(
                    subject=subject,
                    condition="fallback",
                    session=sess,
                    source="fallback",
                    npy_path=str(npy_file),
                    timestamps_path=str(ts_file),
                )
            )

    # stable ordering
    entries.sort(key=lambda e: (e.subject, e.condition, e.session))
    excluded.sort(key=lambda e: (e.subject, e.condition, e.session, e.reason))

    by_subject: Dict[str, int] = {}
    for e in entries:
        by_subject[e.subject] = by_subject.get(e.subject, 0) + 1

    return {
        "policy": "hybrid_mapped_then_fallback",
        "entries": [asdict(e) for e in entries],
        "excluded": [asdict(e) for e in excluded],
        "stats": {
            "num_entries": len(entries),
            "num_excluded": len(excluded),
            "subjects": by_subject,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build healthy pretraining manifest")
    parser.add_argument("--subjects", type=str, default="S1,S2,S3,S4,S5,S6,S7,S8,S9,S10")
    parser.add_argument("--data-root", type=str, default="data/healthy")
    parser.add_argument("--output", type=str, default="manifests/healthy_pretrain_manifest.json")
    args = parser.parse_args()

    subjects = parse_subjects(args.subjects)
    data_root = Path(args.data_root)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    manifest = build_manifest(data_root=data_root, subjects=subjects)

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"Saved manifest: {output_path}")
    print(f"Entries: {manifest['stats']['num_entries']}")
    print(f"Excluded: {manifest['stats']['num_excluded']}")


if __name__ == "__main__":
    main()
