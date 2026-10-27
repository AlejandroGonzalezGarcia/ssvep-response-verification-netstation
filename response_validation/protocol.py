"""Deterministic frame schedule and sinusoidal waveform."""
from dataclasses import asdict, dataclass
import math


@dataclass(frozen=True)
class Trial:
    block: int
    trial_within_block: int
    trial_global: int
    prestimulation_frames: int
    stimulation_frames: int
    iti_frames: int


def build_schedule(config):
    schedule = []
    global_id = 0
    for block in range(1, config.design.blocks + 1):
        for within in range(1, config.design.trials_per_block + 1):
            global_id += 1
            schedule.append(Trial(block, within, global_id,
                                  config.frames(config.timing.prestimulation_s),
                                  config.frames(config.timing.stimulation_s),
                                  config.frames(config.timing.iti_s)))
    return schedule


def opacity(frame_index, frequency_hz, refresh_hz, minimum=0., maximum=1., waveform="sine"):
    if waveform == "square":
        return maximum if (frame_index * frequency_hz / refresh_hz) % 1 < .5 else minimum
    carrier = .5 * (1 + math.cos(2 * math.pi * frequency_hz * frame_index / refresh_hz))
    return minimum + (maximum - minimum) * carrier


def planned_schedule(config):
    return {"preparation_frames": config.frames(config.timing.preparation_s),
            "pulse_frames": {"onset": config.frames(config.diodes.onset.pulse_s),
                             "offset": config.frames(config.diodes.offset.pulse_s)},
            "trials": [asdict(t) for t in build_schedule(config)]}
