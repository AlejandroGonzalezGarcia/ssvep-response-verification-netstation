from pathlib import Path
import unittest

from response_validation.app import _run
from response_validation.config import Config
from response_validation.display import PsychoPyDisplay
from response_validation.markers import Publisher


ROOT = Path(__file__).resolve().parents[1]


class FakeWin:
    def __init__(self):
        self.t = 0.; self.actions = []
    def timeOnFlip(self, record, key): self.actions.append(("time", record, key))
    def callOnFlip(self, callback, *args): self.actions.append(("call", callback, args))
    def flip(self):
        self.t += 1/60
        actions, self.actions = self.actions, []
        for kind, target, value in actions:
            if kind == "time": target[value] = self.t
            else: target(*value)
        return self.t


class FakeDisplay:
    def __init__(self, config):
        self.config = config
        self.win = FakeWin(); self.draws = []; self.screens = []
    def draw(self, **kwargs): self.draws.append(kwargs)
    def poll_abort(self): pass
    def operator_screen(self, text): self.screens.append(text)


class FakeOutput:
    def __init__(self): self.frames = []; self.trials = []; self.local_events = []; self.checkpoints = 0
    def checkpoint(self, *args): self.checkpoints += 1
    def local(self, event, **data): self.local_events.append({"event": event, **data})


class FakeStim:
    def __init__(self, name, order): self.name=name; self.order=order; self.fillColor=None; self.opacity=None
    def draw(self): self.order.append(self.name)


class PresentationTests(unittest.TestCase):
    def setUp(self): self.config = Config.load(ROOT / "config.yaml")

    def test_full_sequence_and_marker_count(self):
        display, output = FakeDisplay(self.config), FakeOutput()
        publisher = Publisher({"run_id": "r", "participant": "001"})
        publisher.publish(publisher.prepare("session_start"))
        _run(display, publisher, output, self.config)
        publisher.publish(publisher.prepare("session_end"))
        self.assertEqual(len(publisher.records), 35)
        self.assertEqual([r["semantic_event"] for r in publisher.records[:4]],
                         ["session_start", "experiment_start", "block_start", "trial_start"])
        self.assertEqual(publisher.records[-2]["semantic_event"], "block_end")
        self.assertEqual(publisher.records[-1]["semantic_event"], "session_end")
        self.assertEqual(len(output.trials), 10)
        self.assertTrue(all(x["status"] == "complete" for x in output.trials))

    def test_pulses_fixation_and_final_iti(self):
        display, output = FakeDisplay(self.config), FakeOutput()
        _run(display, Publisher({"run_id": "r", "participant": "001"}), output, self.config)
        # Skip block preparation. First trial consists of 90 prestim, 600 stim, 60 ITI.
        trial = display.draws[180:180+750]
        self.assertTrue(all(x == {"fixation": True} for x in trial[:90]))
        self.assertTrue(all(x["fixation"] and x["target_opacity"] is not None for x in trial[90:690]))
        self.assertEqual([x["onset"] for x in trial[90:100]], [True]*6 + [False]*4)
        self.assertEqual([x["offset"] for x in trial[690:700]], [True]*6 + [False]*4)
        self.assertTrue(all("target_opacity" not in x and "fixation" not in x for x in trial[690:750]))
        self.assertEqual(output.frames[-1]["phase"], "iti")
        self.assertEqual(output.frames[-1]["frame"], 59)

    def test_real_draw_layers_fixation_after_target(self):
        order = []
        display = PsychoPyDisplay.__new__(PsychoPyDisplay)
        display.target = FakeStim("target", order)
        display.onset = FakeStim("onset", order)
        display.offset = FakeStim("offset", order)
        display.fixation = FakeStim("fixation", order)
        display.text = FakeStim("text", order)
        display.draw(target_opacity=.5, fixation=True)
        self.assertEqual(order, ["target", "onset", "offset", "fixation"])


if __name__ == "__main__":
    unittest.main()
