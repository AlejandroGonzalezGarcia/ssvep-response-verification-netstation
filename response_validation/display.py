"""PsychoPy display, calibrated geometry, timing check, and frame runner."""
from __future__ import annotations

import math
import statistics

from .controls import Controls
from .geometry import circle_geometry, diode_geometry


class Aborted(Exception):
    pass


def validate_refresh(intervals, configured_hz, frequency_hz):
    if len(intervals) != 120 or any(not math.isfinite(x) or x <= 0 for x in intervals):
        raise ValueError("Refresh measurement requires 120 finite positive intervals")
    mean = statistics.mean(intervals)
    sd_ms = statistics.pstdev(intervals) * 1000
    refresh = 1 / mean
    if sd_ms > .2:
        raise ValueError(f"Refresh interval SD {sd_ms:.6f} ms exceeds 0.2 ms")
    if max(intervals) > 1.5 * mean:
        raise ValueError(f"Refresh interval {max(intervals):.9f} s exceeds 1.5 times mean")
    if abs(refresh / configured_hz - 1) > .01:
        raise ValueError(f"Measured {refresh:.6f} Hz differs from configured {configured_hz:.6f} Hz by >1%")
    if frequency_hz >= refresh / 2:
        raise ValueError("Target frequency must be strictly below half measured refresh")
    return {"measured_refresh_hz": refresh, "mean_interval_s": mean, "interval_sd_ms": sd_ms,
            "max_interval_s": max(intervals), "intervals_s": list(intervals)}


class PsychoPyDisplay:
    def __init__(self, config):
        self.win = None
        try:
            self._create(config)
        except BaseException:
            if self.win is not None:
                self.win.close()
            raise

    def _create(self, config):
        from psychopy import event, logging, monitors, visual
        from psychopy.hardware.keyboard import Keyboard
        self.config = config
        self.clock = logging.defaultClock
        monitor = monitors.Monitor("response-validation-display", width=config.calibration.width_cm,
                                   distance=config.calibration.viewing_distance_cm)
        monitor.setSizePix(config.display.resolution_px)
        self.win = visual.Window(size=config.display.resolution_px, screen=config.display.screen_index,
                                 fullscr=config.display.fullscreen, monitor=monitor, units="pix",
                                 color=config.display.background_rgb, colorSpace="rgb1", waitBlanking=True,
                                 checkTiming=False, autoLog=False, allowGUI=not config.display.fullscreen)
        self.info = {"configured_size_px": list(config.display.resolution_px), "screen_index": config.display.screen_index,
                     "observed_size_px": list(map(int, self.win.size)), "keyboard_backend": None,
                     "geometry": {}}
        if self.info["observed_size_px"] != list(config.display.resolution_px):
            raise ValueError(f"Window size mismatch: configured {config.display.resolution_px}, observed {self.win.size}")
        self.controls = Controls(Keyboard(clock=self.clock), event, self.clock)
        self.info["keyboard_backend"] = self.controls.backend
        self.win.mouseVisible = False
        common = {"win": self.win, "units": "pix", "lineColor": None, "autoLog": False}
        target = circle_geometry(config, config.target.center_deg, config.target.diameter_deg)
        fixation = circle_geometry(config, config.fixation.center_deg, config.fixation.diameter_deg)
        onset = diode_geometry(config, config.diodes.onset)
        offset = diode_geometry(config, config.diodes.offset)
        self.info["geometry"] = {"target": target, "fixation": fixation, "onset_diode": onset, "offset_diode": offset}
        self.target = visual.Circle(size=target["size_px"], pos=target["position_px"], edges=256,
                                    fillColor=config.target.color_rgb, colorSpace="rgb1", **common)
        self.fixation = visual.Circle(size=fixation["size_px"], pos=fixation["position_px"], edges=128,
                                      fillColor=config.fixation.color_rgb, colorSpace="rgb1", **common)
        self.onset = visual.Rect(size=onset["size_px"], pos=onset["position_px"], fillColor="black", **common)
        self.offset = visual.Rect(size=offset["size_px"], pos=offset["position_px"], fillColor="black", **common)
        self.text = visual.TextStim(self.win, units="height", color="white", height=.04, wrapWidth=1.5, autoLog=False)

    def draw(self, *, target_opacity=None, fixation=False, onset=False, offset=False, text=None):
        if target_opacity is not None:
            self.target.opacity = target_opacity
            self.target.draw()
        # Diodes are explicitly black outside their pulse.
        self.onset.fillColor = "white" if onset else "black"
        self.offset.fillColor = "white" if offset else "black"
        self.onset.draw()
        self.offset.draw()
        if fixation:
            self.fixation.draw()  # Always after target.
        if text is not None:
            self.text.text = text
            self.text.draw()

    def measure(self):
        self.controls.clear()
        for _ in range(60):
            self.draw()
            self.win.flip()
            self.poll_abort()
        self.win.recordFrameIntervals = True
        self.win.frameIntervals = []
        for _ in range(121):
            self.draw()
            self.win.flip()
            self.poll_abort()
        self.win.recordFrameIntervals = False
        intervals = list(self.win.frameIntervals[-120:])
        result = validate_refresh(intervals, self.config.calibration.refresh_rate_hz, self.config.target.frequency_hz)
        result["observed_size_px_after_measurement"] = list(map(int, self.win.size))
        if result["observed_size_px_after_measurement"] != list(self.config.display.resolution_px):
            raise ValueError("Window size changed during refresh measurement")
        return result

    def poll_abort(self):
        if any(key.name == "escape" for key in self.controls.get(any_key=False)):
            raise Aborted("Escape pressed")

    def operator_screen(self, text):
        self.controls.clear()
        self.draw(text=text)
        self.win.flip()
        while True:
            keys = self.controls.get(any_key=True)
            if any(key.name == "escape" for key in keys):
                raise Aborted("Escape pressed")
            if keys:
                return keys[0].timestamp
            self.draw(text=text)
            self.win.flip()

    def close(self):
        if getattr(self, "win", None) is not None:
            try:
                self.draw()
                return self.win.flip()
            finally:
                self.win.close()


def register_flip(win, publisher, marker, flip_record):
    win.timeOnFlip(flip_record, "time")
    win.callOnFlip(publisher.callback, marker, flip_record)
