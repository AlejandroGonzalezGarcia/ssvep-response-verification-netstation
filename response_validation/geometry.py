"""Visual-angle conversion using physical width and height independently."""
import math


def degrees_to_cm(degrees, distance_cm):
    return 2 * distance_cm * math.tan(math.radians(degrees) / 2)


def extent_px(config, size_deg):
    sx = degrees_to_cm(size_deg[0], config.calibration.viewing_distance_cm)
    sy = degrees_to_cm(size_deg[1], config.calibration.viewing_distance_cm)
    return (sx * config.display.resolution_px[0] / config.calibration.width_cm,
            sy * config.display.resolution_px[1] / config.calibration.height_cm)


def position_px(config, center_deg):
    # Central-angle convention, independently calibrated axes.
    x_cm = config.calibration.viewing_distance_cm * math.tan(math.radians(center_deg[0]))
    y_cm = config.calibration.viewing_distance_cm * math.tan(math.radians(center_deg[1]))
    return (x_cm * config.display.resolution_px[0] / config.calibration.width_cm,
            y_cm * config.display.resolution_px[1] / config.calibration.height_cm)


def circle_geometry(config, center_deg, diameter_deg):
    size = extent_px(config, [diameter_deg, diameter_deg])
    pos = position_px(config, center_deg)
    return _record(size, pos)


def diode_geometry(config, diode):
    width, height = extent_px(config, diode.size_deg)
    fbw, fbh = config.display.resolution_px
    x = fbw / 2 - diode.inset_px - width / 2
    y = fbh / 2 - diode.inset_px - height / 2
    pos = (-x if diode.position.endswith("left") else x,
           y if diode.position.startswith("top") else -y)
    return _record((width, height), pos)


def _record(size, pos):
    width, height = size
    x, y = pos
    return {"size_px": [width, height], "position_px": [x, y],
            "bounds_px": [x - width / 2, y - height / 2, x + width / 2, y + height / 2]}
