"""Experiment lifecycle and the single presentation implementation."""
from __future__ import annotations

from pathlib import Path

from .config import Config
from .display import Aborted, PsychoPyDisplay, register_flip
from .markers import Publisher
from .output import RunOutput
from .protocol import build_schedule, opacity


INTRO = "Central flicker experiment\n\nPress any key to begin.\nPress Escape at any time to stop."
BREAK = "Block complete.\n\nPress any key to continue."
COMPLETE = "Experiment complete.\n\nPress any key to close."


def launch(config_path, participant, mode, config=None):
    config_path = Path(config_path)
    config = config or Config.load(config_path)
    config.validate()
    output_root = (config_path.parent / config.output.root).resolve()
    output = RunOutput(output_root, participant, mode, config, config_path)
    publisher = None
    display = None
    primary = None
    status = "failed"
    try:
        if mode == "netstation":
            from .acquisition import Transport
            transport = Transport(config.netstation)
        elif mode == "test":
            transport = None
        else:
            raise ValueError("Mode must be test or netstation")
        publisher = Publisher(output.common, transport)
        publisher.start()  # Recording begins before intro.
        publisher.publish(publisher.prepare("session_start"))
        display = PsychoPyDisplay(config)
        try:
            output.metadata["display"] = display.info
            output.metadata["refresh"] = display.measure()
        except BaseException as exc:
            output.metadata["display"] = display.info
            output.metadata["refresh_rejected"] = {"error": f"{type(exc).__name__}: {exc}",
                                                    "frame_intervals": list(getattr(display.win, "frameIntervals", []))}
            raise
        output.checkpoint(publisher.records, publisher.snapshot())
        display.operator_screen(INTRO)
        _run(display, publisher, output, config)
        # Session end is enqueued before cleanup; cleanup completes before dismissal.
        publisher.publish(publisher.prepare("session_end"))
        publisher.checkpoint()
        publisher.close()
        output.finish("complete", publisher.records, publisher.snapshot())
        status = "complete"
        display.operator_screen(COMPLETE)
        return 0
    except Aborted as exc:
        primary = exc
        status = "aborted"
    except BaseException as exc:
        primary = exc
        status = "failed"
    finally:
        cleanup = []
        if display is not None:
            try:
                removal_time = display.close()  # Clear visuals before remaining acquisition cleanup.
                if status != "complete":
                    output.local("abort_removal", psychopy_time=removal_time)
            except BaseException as exc:
                cleanup.append(f"display: {type(exc).__name__}: {exc}")
        if publisher is not None and not publisher.closed:
            try:
                if publisher.transport is None or publisher.transport.failure is None:
                    publisher.publish(publisher.prepare("session_end"))
            except BaseException as exc:
                cleanup.append(f"session_end: {type(exc).__name__}: {exc}")
            try:
                publisher.close()
            except BaseException as exc:
                cleanup.append(f"acquisition: {type(exc).__name__}: {exc}")
        if status != "complete":
            message = None if primary is None else f"{type(primary).__name__}: {primary}"
            if cleanup:
                message = f"{message or ''}; cleanup: {'; '.join(cleanup)}"
            records = [] if publisher is None else publisher.records
            snapshot = None if publisher is None else publisher.snapshot()
            output.finish(status, records, snapshot, message)
    if isinstance(primary, Aborted):
        return 130
    if primary is not None:
        raise primary
    return 1


def _run(display, publisher, output, config):
    schedule = build_schedule(config)
    by_block = {block: [t for t in schedule if t.block == block] for block in range(1, config.design.blocks + 1)}
    onset_frames = config.frames(config.diodes.onset.pulse_s)
    offset_frames = config.frames(config.diodes.offset.pulse_s)
    for block, trials in by_block.items():
        if block > 1:
            display.operator_screen(BREAK)
        expr = publisher.prepare("experiment_start") if block == 1 else None
        blst = publisher.prepare("block_start", block=block)
        for frame in range(config.frames(config.timing.preparation_s)):
            flip = {}
            if frame == 0:
                if expr is not None:
                    register_flip(display.win, publisher, expr, flip)
                register_flip(display.win, publisher, blst, flip)
            display.draw()
            timestamp = display.win.flip()
            _record_frame(output, {"phase": "preparation", "block": block, "frame": frame,
                                   "target_opacity": None, "fixation": False,
                                   "onset_diode": False, "offset_diode": False}, timestamp, config)
            display.poll_abort(); publisher.check()
        for trial in trials:
            row = {"block": block, "trial_within_block": trial.trial_within_block,
                   "trial_global": trial.trial_global, "status": "started",
                   "planned_prestimulation_frames": trial.prestimulation_frames,
                   "planned_stimulation_frames": trial.stimulation_frames,
                   "planned_iti_frames": trial.iti_frames}
            output.trials.append(row)
            first_trial_frame = len(output.frames)
            trst = publisher.prepare("trial_start", block=block, trial_global=trial.trial_global,
                                     trial_within_block=trial.trial_within_block, frequency_hz=config.target.frequency_hz)
            ston = publisher.prepare("stimulus_onset", block=block, trial_global=trial.trial_global,
                                     trial_within_block=trial.trial_within_block, frequency_hz=config.target.frequency_hz)
            stof = publisher.prepare("stimulus_offset", block=block, trial_global=trial.trial_global,
                                     trial_within_block=trial.trial_within_block, frequency_hz=config.target.frequency_hz)
            _phase(display, publisher, output, "prestimulation", trial, trial.prestimulation_frames,
                   lambda _: {"fixation": True}, trst)
            _phase(display, publisher, output, "stimulation", trial, trial.stimulation_frames,
                   lambda n: {"target_opacity": opacity(n, config.target.frequency_hz, config.calibration.refresh_rate_hz,
                                                        config.target.opacity_min, config.target.opacity_max,
                                                        config.target.waveform),
                              "fixation": True, "onset": n < onset_frames}, ston)
            _phase(display, publisher, output, "iti", trial, trial.iti_frames,
                   lambda n: {"offset": n < offset_frames}, stof)
            trial_frames = output.frames[first_trial_frame:]
            row.update(status="complete", actual_prestimulation_frames=trial.prestimulation_frames,
                       actual_stimulation_frames=trial.stimulation_frames, actual_iti_frames=trial.iti_frames,
                       long_frames=sum(bool(frame["long_frame"]) for frame in trial_frames),
                       estimated_missed_refreshes=sum(frame["estimated_missed_refreshes"] for frame in trial_frames))
        blen = publisher.prepare("block_end", block=block)
        flip = {}
        register_flip(display.win, publisher, blen, flip)
        display.draw(text=COMPLETE if block == config.design.blocks else BREAK)
        display.win.flip()
        publisher.checkpoint()
        output.checkpoint(publisher.records, publisher.snapshot())


def _phase(display, publisher, output, name, trial, count, draw_args, first_marker):
    previous_onset = previous_offset = False
    for frame in range(count):
        flip = {}
        if frame == 0:
            register_flip(display.win, publisher, first_marker, flip)
        state = draw_args(frame)
        display.draw(**state)
        timestamp = display.win.flip()
        if frame == 0:
            output.trials[-1][f"{name}_onset_time"] = timestamp
            if name == "iti":
                output.trials[-1]["stimulus_offset_time"] = timestamp
                held_from = output.trials[-1].get("last_stimulation_flip_time")
                output.trials[-1]["last_stimulation_held_interval_s"] = None if held_from is None else timestamp - held_from
        onset_active = bool(state.get("onset", False))
        offset_active = bool(state.get("offset", False))
        _record_frame(output, {"phase": name, "block": trial.block, "trial_global": trial.trial_global,
                               "frame": frame, "target_opacity": state.get("target_opacity"),
                               "fixation": bool(state.get("fixation", False)),
                               "onset_diode": onset_active, "offset_diode": offset_active}, timestamp, display.config)
        if onset_active != previous_onset:
            output.local("onset_diode_start" if onset_active else "onset_diode_end",
                         block=trial.block, trial_global=trial.trial_global, psychopy_time=timestamp)
        if offset_active != previous_offset:
            output.local("offset_diode_start" if offset_active else "offset_diode_end",
                         block=trial.block, trial_global=trial.trial_global, psychopy_time=timestamp)
        previous_onset, previous_offset = onset_active, offset_active
        display.poll_abort()
        publisher.check()
    # Offset flip serves as the last stimulation frame's held-interval endpoint.
    if name == "stimulation":
        output.trials[-1]["last_stimulation_flip_time"] = output.frames[-1]["flip_time"]
    output.trials[-1][f"{name}_last_flip_time"] = output.frames[-1]["flip_time"]


def _record_frame(output, data, timestamp, config):
    previous = output.frames[-1]["flip_time"] if output.frames else None
    interval = None if previous is None else timestamp - previous
    nominal = 1 / config.calibration.refresh_rate_hz
    output.frames.append({**data, "flip_time": timestamp, "interval_s": interval,
                          "long_frame": False if interval is None else interval > 1.5 * nominal,
                          "estimated_missed_refreshes": 0 if interval is None else max(0, round(interval / nominal) - 1)})
