"""Marker contract shared by simulated and NetStation modes."""
from __future__ import annotations

from dataclasses import dataclass
import math
import time


EVENT_CODES = {
    "session_start": "SESS", "experiment_start": "EXPR", "block_start": "BLST",
    "trial_start": "TRST", "stimulus_onset": "STON", "stimulus_offset": "STOF",
    "block_end": "BLEN", "session_end": "SESE",
}


def validate_metadata(data):
    if not isinstance(data, dict) or len(data) > 255:
        raise ValueError("NetStation metadata must be a mapping with at most 255 fields")
    estimated = 300
    for key, value in data.items():
        if not isinstance(key, str) or len(key) != 4 or not key.isascii():
            raise ValueError(f"Invalid four-character ASCII metadata key: {key!r}")
        if type(value) is int and not -(2**31) <= value < 2**31:
            raise ValueError(f"{key} integer is outside signed 32-bit range")
        if type(value) is float and not math.isfinite(value):
            raise ValueError(f"{key} float must be finite")
        if type(value) is str and (not value.isascii() or len(value.encode("ascii")) > 65535):
            raise ValueError(f"{key} string must be ASCII and <=65535 bytes")
        if type(value) not in (bool, int, float, str):
            raise ValueError(f"{key} has unsupported type {type(value).__name__}")
        estimated += 12 + (len(value) if type(value) is str else 8)
    if estimated > 65535:
        raise ValueError("NetStation event exceeds conservative packet size")


@dataclass(frozen=True)
class PreparedMarker:
    event: str
    code: str
    data: dict
    trial_global: int = 0
    block: int | None = None
    trial_within_block: int | None = None


class Publisher:
    def __init__(self, common, transport=None):
        if len(EVENT_CODES) != len(set(EVENT_CODES.values())):
            raise ValueError("Marker codes collide")
        self.common = common
        self.transport = transport
        self.records = []
        self.closed = False

    def prepare(self, event, *, block=None, trial_global=0, trial_within_block=None, frequency_hz=None):
        if event not in EVENT_CODES:
            raise ValueError(f"Unknown semantic event: {event}")
        data = {"RUID": self.common["run_id"], "PART": self.common["participant"]}
        if block is not None:
            data["BLOC"] = int(block)
        if trial_global:
            data["TRIA"] = int(trial_global)
        if trial_within_block is not None:
            data["TWIN"] = int(trial_within_block)
        if frequency_hz is not None:
            data["FREQ"] = float(frequency_hz)
        validate_metadata({**data, "MSEQ": 2147483647})
        return PreparedMarker(event, EVENT_CODES[event], data, trial_global, block, trial_within_block)

    def publish(self, marker, flip_record=None, capture_time=None):
        if self.closed:
            raise RuntimeError("Marker publication after publisher close")
        sequence = len(self.records) + 1
        if self.transport is not None and capture_time is None:
            capture_time = self.transport.capture_time()
        record = {
            "sequence": sequence, "semantic_event": marker.event, "code": marker.code,
            "trial_global": marker.trial_global, "block": marker.block,
            "trial_within_block": marker.trial_within_block,
            "psychopy_time": flip_record.get("time") if flip_record else None,
            "capture_time": capture_time, "duration_s": .001,
            "metadata": {**marker.data, "MSEQ": sequence},
            "queued_monotonic": time.monotonic(),
            "disposition": "simulated" if self.transport is None else "pending",
        }
        self.records.append(record)
        if self.transport is not None:
            self.transport.enqueue(record)
        return record

    def callback(self, marker, flip_record):
        capture = self.transport.capture_time() if self.transport is not None else None
        self.publish(marker, flip_record, capture)

    def start(self):
        if self.transport is not None:
            self.transport.start()

    def check(self):
        if self.transport is not None:
            self.transport.check()

    def checkpoint(self):
        if self.transport is not None:
            self.transport.checkpoint()

    def close(self):
        if self.closed:
            return
        self.closed = True
        if self.transport is not None:
            self.transport.stop()

    def snapshot(self):
        return {"backend": "test" if self.transport is None else "netstation",
                "transport": None if self.transport is None else self.transport.snapshot()}
