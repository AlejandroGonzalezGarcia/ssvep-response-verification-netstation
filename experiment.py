"""Participant launcher; configuration is resolved beside this file."""
import argparse
from pathlib import Path

from response_validation.config import participant_id


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Central sinusoidal SSVEP experiment")
    parser.add_argument("--participant", required=True)
    parser.add_argument("--mode", required=True, type=str.lower, choices=("test", "netstation"))
    args = parser.parse_args(argv)
    try:
        participant_id(args.participant)
    except ValueError as exc:
        parser.error(str(exc))
    return args


def main(argv=None):
    args = parse_args(argv)
    from response_validation.app import launch
    try:
        return launch(Path(__file__).with_name("config.yaml"), args.participant, args.mode)
    except KeyboardInterrupt:
        print("Experiment interrupted; cleanup was attempted.")
        return 130
    except (ValueError, RuntimeError, OSError) as exc:
        print(f"Experiment could not run: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
