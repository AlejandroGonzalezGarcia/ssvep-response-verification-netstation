"""Unique run allocation and atomic local evidence."""
from __future__ import annotations

import csv
from datetime import datetime, timezone
import importlib.metadata
import io
import json
import os
from pathlib import Path
import platform
import re
import uuid

import yaml

from .config import participant_id
from .protocol import planned_schedule


def atomic_text(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as stream:
        stream.write(value)
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def allocate(root, participant):
    parent = Path(root) / participant_id(participant)
    parent.mkdir(parents=True, exist_ok=True)
    while True:
        used = [int(match.group(1)) for item in parent.iterdir()
                if (match := re.fullmatch(r"run(\d+)", item.name))]
        candidate = parent / f"run{max(used, default=0)+1:03d}"
        try:
            candidate.mkdir()
            return candidate
        except FileExistsError:
            pass


class RunOutput:
    def __init__(self, root, participant, mode, config, source):
        self.path = allocate(root, participant)
        self.common = {"participant": participant, "mode": mode, "run_id": str(uuid.uuid4())}
        self.trials, self.frames, self.local_events = [], [], []
        versions = {}
        for package in ("psychopy", "pyglet", "numpy", "PyYAML", "egi-pynetstation"):
            try:
                versions[package] = importlib.metadata.version(package)
            except importlib.metadata.PackageNotFoundError:
                versions[package] = None
        self.metadata = {**self.common, "status": "starting", "started_utc": datetime.now(timezone.utc).isoformat(),
                         "python": platform.python_version(), "platform": platform.platform(), "versions": versions,
                         "config_source": str(Path(source).resolve()),
                         "clock_policy": "PsychoPy flip times, EGI captured/converted times, and physical photodiode times are distinct.",
                         "checkpoint_policy": "Checkpointed before presentation and after blocks; a hard crash can lose the active block."}
        atomic_text(self.path / "config_source.yaml", Path(source).read_text(encoding="utf-8"))
        atomic_text(self.path / "config_resolved.yaml", yaml.safe_dump(config.snapshot(), sort_keys=False))
        atomic_text(self.path / "schedule.json", json.dumps(planned_schedule(config), indent=2))
        self.checkpoint([])

    def local(self, event, **data):
        self.local_events.append({"event": event, **data})

    def checkpoint(self, markers, acquisition=None):
        atomic_text(self.path / "run_metadata.json", json.dumps(self.metadata, indent=2, allow_nan=False))
        atomic_text(self.path / "trials.json", json.dumps(self.trials, indent=2, allow_nan=False))
        atomic_text(self.path / "frames.json", json.dumps(self.frames, indent=2, allow_nan=False))
        atomic_text(self.path / "local_events.json", json.dumps(self.local_events, indent=2, allow_nan=False))
        atomic_text(self.path / "markers.json", json.dumps(markers, indent=2, allow_nan=False))
        acknowledged = [r for r in markers if r.get("disposition") == "acknowledged"]
        fields = ["sequence", "semantic_event", "code", "block", "trial_global", "trial_within_block",
                  "psychopy_time", "capture_time", "natural_start_s", "transmitted_ms", "adjustment_ms", "disposition"]
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(acknowledged)
        atomic_text(self.path / "markers.csv", stream.getvalue())
        if acquisition is not None:
            atomic_text(self.path / "acquisition.json", json.dumps(acquisition, indent=2, allow_nan=False))

    def finish(self, status, markers, acquisition=None, error=None):
        self.metadata.update(status=status, finished_utc=datetime.now(timezone.utc).isoformat(), error=error)
        self.checkpoint(markers, acquisition)
