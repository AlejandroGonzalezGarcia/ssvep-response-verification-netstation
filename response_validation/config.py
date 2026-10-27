"""Strict YAML configuration and protocol validation."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
import ipaddress
import math
from pathlib import Path
import re
from typing import Any

import yaml


class UniqueLoader(yaml.SafeLoader):
    pass


def _unique_mapping(loader, node, deep=False):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in result:
            raise ValueError(f"Duplicate configuration key: {key}")
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _unique_mapping)


def _number(value: Any, name: str, *, low=None, high=None, positive=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    if positive and value <= 0:
        raise ValueError(f"{name} must be positive")
    if low is not None and value < low or high is not None and value > high:
        raise ValueError(f"{name} must be between {low} and {high}")


def _integer(value: Any, name: str, minimum=0):
    if type(value) is not int or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")


def _pair(value, name, *, positive=False):
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError(f"{name} must contain exactly two values")
    for item in value:
        _number(item, name, positive=positive)


def participant_id(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        raise ValueError("Participant must contain only letters, digits, underscore, or hyphen")
    if value.upper() in {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}:
        raise ValueError("Participant is a reserved filename")
    return value


@dataclass(frozen=True)
class Display:
    screen_index: int = 1
    resolution_px: list[int] = field(default_factory=lambda: [1920, 1080])
    fullscreen: bool = True
    background_rgb: list[float] = field(default_factory=lambda: [.5, .5, .5])


@dataclass(frozen=True)
class Calibration:
    width_cm: float = 58.0
    height_cm: float = 33.0
    viewing_distance_cm: float = 57.6
    refresh_rate_hz: float = 60.0


@dataclass(frozen=True)
class Design:
    blocks: int = 1
    trials_per_block: int = 10


@dataclass(frozen=True)
class Timing:
    preparation_s: float = 3.0
    prestimulation_s: float = 1.5
    stimulation_s: float = 10.0
    iti_s: float = 1.0


@dataclass(frozen=True)
class Target:
    center_deg: list[float] = field(default_factory=lambda: [0., 0.])
    diameter_deg: float = 2.0
    color_rgb: list[float] = field(default_factory=lambda: [1., 1., 1.])
    frequency_hz: float = 15.0
    waveform: str = "sine"
    opacity_min: float = 0.0
    opacity_max: float = 1.0


@dataclass(frozen=True)
class Fixation:
    center_deg: list[float] = field(default_factory=lambda: [0., 0.])
    diameter_deg: float = .5
    color_rgb: list[float] = field(default_factory=lambda: [1., 0., 0.])


@dataclass(frozen=True)
class Diode:
    position: str = "top_left"
    size_deg: list[float] = field(default_factory=lambda: [2., 2.])
    inset_px: int = 0
    pulse_s: float = .1


@dataclass(frozen=True)
class Diodes:
    onset: Diode = field(default_factory=Diode)
    offset: Diode = field(default_factory=lambda: Diode(position="bottom_left"))


@dataclass(frozen=True)
class NetStation:
    eci_ip: str = "10.10.10.42"
    port: int = 55513
    ntp_ip: str = "10.10.10.51"
    queue_capacity: int = 4096
    operation_timeout_s: float = 15.0


@dataclass(frozen=True)
class Output:
    root: str = "data/results"


@dataclass(frozen=True)
class Config:
    display: Display = field(default_factory=Display)
    calibration: Calibration = field(default_factory=Calibration)
    design: Design = field(default_factory=Design)
    timing: Timing = field(default_factory=Timing)
    target: Target = field(default_factory=Target)
    fixation: Fixation = field(default_factory=Fixation)
    diodes: Diodes = field(default_factory=Diodes)
    netstation: NetStation = field(default_factory=NetStation)
    output: Output = field(default_factory=Output)

    @classmethod
    def load(cls, path: Path | str) -> "Config":
        raw = yaml.load(Path(path).read_text(encoding="utf-8"), Loader=UniqueLoader)
        if not isinstance(raw, dict):
            raise ValueError("Configuration must be a mapping")
        result = _construct(cls(), raw, "config")
        result.validate()
        return result

    def frames(self, seconds: float) -> int:
        return round(seconds * self.calibration.refresh_rate_hz)

    def snapshot(self):
        return asdict(self)

    def validate(self):
        d, c, t, target = self.display, self.calibration, self.timing, self.target
        _integer(d.screen_index, "display.screen_index")
        if type(d.fullscreen) is not bool:
            raise ValueError("display.fullscreen must be boolean")
        _pair(d.resolution_px, "display.resolution_px", positive=True)
        for x in d.resolution_px:
            _integer(x, "display.resolution_px", 1)
        _rgb(d.background_rgb, "display.background_rgb")
        for name in ("width_cm", "height_cm", "viewing_distance_cm", "refresh_rate_hz"):
            _number(getattr(c, name), f"calibration.{name}", positive=True)
        _integer(self.design.blocks, "design.blocks", 1)
        _integer(self.design.trials_per_block, "design.trials_per_block", 1)
        for name in ("preparation_s", "prestimulation_s", "stimulation_s", "iti_s"):
            value = getattr(t, name)
            _number(value, f"timing.{name}", positive=True)
            if self.frames(value) < 1:
                raise ValueError(f"timing.{name} must span at least one frame")
        _pair(target.center_deg, "target.center_deg")
        _number(target.diameter_deg, "target.diameter_deg", positive=True)
        _rgb(target.color_rgb, "target.color_rgb")
        _number(target.frequency_hz, "target.frequency_hz", positive=True)
        if target.waveform not in {"sine", "square"}:
            raise ValueError('target.waveform must be either "sine" or "square"')
        if target.frequency_hz >= c.refresh_rate_hz / 2:
            raise ValueError("target.frequency_hz must be below half configured refresh")
        _number(target.opacity_min, "target.opacity_min", low=0, high=1)
        _number(target.opacity_max, "target.opacity_max", low=0, high=1)
        if target.opacity_min >= target.opacity_max:
            raise ValueError("target opacity_min must be below opacity_max")
        _pair(self.fixation.center_deg, "fixation.center_deg")
        _number(self.fixation.diameter_deg, "fixation.diameter_deg", positive=True)
        _rgb(self.fixation.color_rgb, "fixation.color_rgb")
        if self.fixation.center_deg != target.center_deg:
            raise ValueError("Target and fixation centers must match")
        for name, diode, containing in (("onset", self.diodes.onset, t.stimulation_s), ("offset", self.diodes.offset, t.iti_s)):
            if diode.position not in {"top_left", "top_right", "bottom_left", "bottom_right"}:
                raise ValueError(f"diodes.{name}.position is invalid")
            _pair(diode.size_deg, f"diodes.{name}.size_deg", positive=True)
            _integer(diode.inset_px, f"diodes.{name}.inset_px")
            _number(diode.pulse_s, f"diodes.{name}.pulse_s", positive=True)
            if self.frames(diode.pulse_s) < 1 or self.frames(diode.pulse_s) > self.frames(containing):
                raise ValueError(f"diodes.{name}.pulse_s must span a frame and fit its phase")
        self._validate_geometry()
        for name in ("eci_ip", "ntp_ip"):
            try:
                ipaddress.IPv4Address(getattr(self.netstation, name))
            except Exception as exc:
                raise ValueError(f"netstation.{name} must be an IPv4 address") from exc
        _integer(self.netstation.port, "netstation.port", 1)
        if self.netstation.port > 65535:
            raise ValueError("netstation.port must be <= 65535")
        _integer(self.netstation.queue_capacity, "netstation.queue_capacity", 1)
        _number(self.netstation.operation_timeout_s, "netstation.operation_timeout_s", positive=True)
        if not isinstance(self.output.root, str) or not self.output.root:
            raise ValueError("output.root must be a nonempty path")

    def _validate_geometry(self):
        from .geometry import circle_geometry, diode_geometry
        width, height = self.display.resolution_px
        items = [circle_geometry(self, self.target.center_deg, self.target.diameter_deg),
                 circle_geometry(self, self.fixation.center_deg, self.fixation.diameter_deg),
                 diode_geometry(self, self.diodes.onset), diode_geometry(self, self.diodes.offset)]
        for item in items:
            left, bottom, right, top = item["bounds_px"]
            if left < -width / 2 or right > width / 2 or bottom < -height / 2 or top > height / 2:
                raise ValueError(f"Configured geometry is outside the framebuffer: {item}")


def _rgb(value, name):
    if not isinstance(value, list) or len(value) != 3:
        raise ValueError(f"{name} must contain three channels")
    for channel in value:
        _number(channel, name, low=0, high=1)


def _construct(default, values, path):
    if not isinstance(values, dict):
        raise ValueError(f"{path} must be a mapping")
    allowed = {f.name for f in fields(default)}
    unknown = values.keys() - allowed
    if unknown:
        raise ValueError(f"Unknown fields in {path}: {', '.join(sorted(unknown))}")
    kwargs = {}
    for key, value in values.items():
        current = getattr(default, key)
        kwargs[key] = _construct(current, value, f"{path}.{key}") if hasattr(current, "__dataclass_fields__") else value
    return type(default)(**kwargs)
