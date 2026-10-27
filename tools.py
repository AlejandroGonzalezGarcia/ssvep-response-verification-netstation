"""Developer tools. These never start NetStation acquisition."""
import argparse
from dataclasses import replace
import json
from pathlib import Path

from response_validation.config import Config
from response_validation.geometry import circle_geometry, diode_geometry
from response_validation.protocol import build_schedule, planned_schedule


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("validate", "inspect-netstation", "check-display", "preview-geometry", "pilot"))
    parser.add_argument("--config", type=Path, default=Path(__file__).with_name("config.yaml"))
    parser.add_argument("--participant", default="SOFTWARE_PILOT")
    args = parser.parse_args(argv)
    config = Config.load(args.config)
    if args.action == "validate":
        print(json.dumps({"ok": True, "trials": len(build_schedule(config)), "schedule": planned_schedule(config)}, indent=2))
        return 0
    if args.action == "inspect-netstation":
        from response_validation.acquisition import inspect_package
        print(json.dumps(inspect_package(), indent=2, default=str))
        return 0
    if args.action in {"check-display", "preview-geometry"}:
        from response_validation.display import PsychoPyDisplay
        display = None
        try:
            display = PsychoPyDisplay(config)
            if args.action == "check-display":
                print(json.dumps({"display": display.info, "refresh": display.measure()}, indent=2))
            else:
                display.operator_screen("Geometry preview\n\nCentral target and fixation; onset top-left, offset bottom-left.\nPress any key to close.")
                print(json.dumps(display.info, indent=2))
            return 0
        finally:
            if display is not None:
                display.close()
    from response_validation.app import launch
    pilot = replace(config,
                    design=replace(config.design, blocks=1, trials_per_block=1),
                    timing=replace(config.timing, preparation_s=.5, prestimulation_s=.5,
                                   stimulation_s=2., iti_s=.5))
    pilot.validate()
    return launch(args.config, args.participant, "test", config=pilot)


if __name__ == "__main__":
    raise SystemExit(main())
