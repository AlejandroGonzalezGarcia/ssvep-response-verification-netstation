"""Backend-aware keyboard polling with one experiment clock."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Key:
    name: str
    timestamp: float


class Controls:
    def __init__(self, keyboard, event_module, clock):
        self.keyboard, self.event, self.clock = keyboard, event_module, clock
        self.backend = keyboard.getBackend()

    def clear(self):
        if self.backend == "event":
            self.event.clearEvents(eventType="keyboard")
        else:
            self.keyboard.clearEvents()

    def get(self, any_key=False):
        names = None if any_key else ["escape"]
        if self.backend == "event":
            pairs = self.event.getKeys(keyList=names, timeStamped=self.clock)
        else:
            pairs = [(key.name, key.rt) for key in self.keyboard.getKeys(keyList=names, waitRelease=False, clear=True)]
        return [Key("return" if name in {"enter", "num_enter"} else name, float(stamp)) for name, stamp in pairs]
