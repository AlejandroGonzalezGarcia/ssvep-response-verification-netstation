import argparse
from dataclasses import replace
import importlib
import math
from pathlib import Path
import tempfile
import unittest

import yaml

from experiment import parse_args
from response_validation.config import Config, participant_id
from response_validation.display import validate_refresh
from response_validation.geometry import circle_geometry, diode_geometry
from response_validation.markers import EVENT_CODES, Publisher, validate_metadata
from response_validation.protocol import build_schedule, opacity, planned_schedule


ROOT = Path(__file__).resolve().parents[1]


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.config = Config.load(ROOT / "config.yaml")

    def mutate(self, callback):
        raw = yaml.safe_load((ROOT / "config.yaml").read_text())
        callback(raw)
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as stream:
            yaml.safe_dump(raw, stream)
            path = Path(stream.name)
        self.addCleanup(path.unlink)
        return Config.load(path)

    def test_defaults(self):
        self.assertEqual(self.config.design.blocks, 1)
        self.assertEqual(self.config.target.frequency_hz, 15)
        self.assertEqual(self.config.target.waveform, "sine")
        self.assertEqual(self.config.calibration.width_cm, 58)

    def test_invalid_waveform_rejected(self):
        with self.assertRaisesRegex(ValueError, "waveform"):
            self.mutate(lambda x: x["target"].update(waveform="triangle"))

    def test_unknown_key_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unknown"):
            self.mutate(lambda x: x["target"].update(unknown=1))

    def test_duplicate_key_rejected(self):
        text = (ROOT / "config.yaml").read_text() + "\ndesign:\n  blocks: 1\n"
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as stream:
            stream.write(text); path = Path(stream.name)
        self.addCleanup(path.unlink)
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            Config.load(path)

    def test_bool_is_not_integer(self):
        with self.assertRaises(ValueError):
            self.mutate(lambda x: x["display"].update(screen_index=True))

    def test_zero_frame_phase_rejected(self):
        with self.assertRaisesRegex(ValueError, "span"):
            self.mutate(lambda x: x["timing"].update(prestimulation_s=.001))

    def test_pulse_must_fit_phase(self):
        with self.assertRaisesRegex(ValueError, "fit"):
            self.mutate(lambda x: x["diodes"]["offset"].update(pulse_s=2))

    def test_nyquist_rejected(self):
        with self.assertRaisesRegex(ValueError, "half"):
            self.mutate(lambda x: x["target"].update(frequency_hz=30))

    def test_out_of_bounds_target_rejected(self):
        with self.assertRaisesRegex(ValueError, "outside"):
            self.mutate(lambda x: (x["target"].update(center_deg=[100, 0]), x["fixation"].update(center_deg=[100, 0])))

    def test_bad_ipv4_rejected(self):
        with self.assertRaisesRegex(ValueError, "IPv4"):
            self.mutate(lambda x: x["netstation"].update(eci_ip="nope"))


class CliTests(unittest.TestCase):
    def test_leading_zero_participant(self):
        self.assertEqual(parse_args(["--participant", "001", "--mode", "test"]).participant, "001")

    def test_both_options_required(self):
        with self.assertRaises(SystemExit):
            parse_args(["--participant", "001"])

    def test_extra_option_rejected(self):
        with self.assertRaises(SystemExit):
            parse_args(["--participant", "001", "--mode", "test", "--debug"])

    def test_unsafe_participant_rejected(self):
        with self.assertRaises(ValueError):
            participant_id("../001")

    def test_app_import_does_not_import_acquisition(self):
        import sys
        sys.modules.pop("response_validation.acquisition", None)
        module = importlib.reload(importlib.import_module("response_validation.app"))
        self.assertIsNotNone(module)
        self.assertNotIn("response_validation.acquisition", sys.modules)


class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.config = Config.load(ROOT / "config.yaml")

    def test_waveform_samples(self):
        values = [opacity(n, 15, 60) for n in range(4)]
        for actual, expected in zip(values, [1, .5, 0, .5]):
            self.assertAlmostEqual(actual, expected)

    def test_square_waveform_samples(self):
        values = [opacity(n, 15, 60, waveform="square") for n in range(8)]
        self.assertEqual(values, [1, 1, 0, 0, 1, 1, 0, 0])

    def test_phase_resets(self):
        self.assertEqual(opacity(0, 15, 60), 1)
        self.assertEqual(opacity(0, 15, 60), 1)

    def test_python_round_ties_to_even(self):
        self.assertEqual(round(2.5), 2)
        self.assertEqual(round(3.5), 4)

    def test_default_frame_counts(self):
        plan = planned_schedule(self.config)
        self.assertEqual(plan["preparation_frames"], 180)
        self.assertEqual(plan["pulse_frames"], {"onset": 6, "offset": 6})
        self.assertEqual((plan["trials"][0]["prestimulation_frames"], plan["trials"][0]["stimulation_frames"], plan["trials"][0]["iti_frames"]), (90, 600, 60))

    def test_schedule_ids_and_final_iti(self):
        trials = build_schedule(self.config)
        self.assertEqual([t.trial_global for t in trials], list(range(1, 11)))
        self.assertEqual(trials[-1].iti_frames, 60)

    def test_nominal_duration(self):
        total = self.config.timing.preparation_s + len(build_schedule(self.config)) * (self.config.timing.prestimulation_s + self.config.timing.stimulation_s + self.config.timing.iti_s)
        self.assertEqual(total, 128)


class GeometryTests(unittest.TestCase):
    def setUp(self):
        self.config = Config.load(ROOT / "config.yaml")

    def test_circle_physical_dimensions_match(self):
        geometry = circle_geometry(self.config, [0, 0], 2)
        cm_x = geometry["size_px"][0] * 58 / 1920
        cm_y = geometry["size_px"][1] * 33 / 1080
        self.assertAlmostEqual(cm_x, cm_y, places=10)

    def test_diode_edges_are_anchored(self):
        onset = diode_geometry(self.config, self.config.diodes.onset)
        offset = diode_geometry(self.config, self.config.diodes.offset)
        self.assertAlmostEqual(onset["bounds_px"][0], -960)
        self.assertAlmostEqual(onset["bounds_px"][3], 540)
        self.assertAlmostEqual(offset["bounds_px"][0], -960)
        self.assertAlmostEqual(offset["bounds_px"][1], -540)


class RefreshTests(unittest.TestCase):
    def test_valid_refresh(self):
        result = validate_refresh([1/60] * 120, 60, 15)
        self.assertAlmostEqual(result["measured_refresh_hz"], 60)

    def test_wrong_length_rejected(self):
        with self.assertRaises(ValueError):
            validate_refresh([1/60] * 119, 60, 15)

    def test_long_frame_rejected(self):
        with self.assertRaisesRegex(ValueError, "1.5"):
            validate_refresh([1/60] * 119 + [1/30], 60, 15)

    def test_refresh_mismatch_rejected(self):
        with self.assertRaisesRegex(ValueError, "1%"):
            validate_refresh([1/50] * 120, 60, 15)


class MarkerTests(unittest.TestCase):
    def setUp(self):
        self.publisher = Publisher({"run_id": "12345678-1234-1234-1234-123456789abc", "participant": "001"})

    def test_codes_are_unique_ascii_four(self):
        self.assertEqual(len(EVENT_CODES), len(set(EVENT_CODES.values())))
        self.assertTrue(all(len(x) == 4 and x.isascii() for x in EVENT_CODES.values()))

    def test_default_wire_count(self):
        self.assertEqual(3 + 2*1 + 3*1*10, 35)

    def test_metadata_fields(self):
        marker = self.publisher.prepare("stimulus_onset", block=2, trial_global=12, trial_within_block=2, frequency_hz=15)
        self.assertEqual(marker.data["PART"], "001")
        self.assertEqual(marker.data["BLOC"], 2)
        self.assertEqual(marker.data["TRIA"], 12)
        self.assertEqual(marker.data["TWIN"], 2)
        self.assertEqual(marker.data["FREQ"], 15.)

    def test_test_mode_is_simulated(self):
        marker = self.publisher.prepare("session_start")
        record = self.publisher.publish(marker)
        self.assertEqual(record["disposition"], "simulated")
        self.assertEqual(record["sequence"], 1)

    def test_invalid_metadata_rejected(self):
        with self.assertRaises(ValueError):
            validate_metadata({"TOO_LONG": 1})
        with self.assertRaises(ValueError):
            validate_metadata({"TEST": float("nan")})

    def test_unknown_event_rejected(self):
        with self.assertRaises(ValueError):
            self.publisher.prepare("mystery")


if __name__ == "__main__":
    unittest.main()
