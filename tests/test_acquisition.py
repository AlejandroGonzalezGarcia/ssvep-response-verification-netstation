import threading
import unittest
from dataclasses import replace

from response_validation.acquisition import Transport
from response_validation.config import Config
from response_validation.markers import Publisher
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class FakeStation:
    def __init__(self, ip, port):
        self.ip, self.port = ip, port
        self.calls = []
        self.times = iter([1.0004, 1.0004, 1.002])

    def connect(self, **kwargs): self.calls.append(("connect", kwargs))
    def begin_rec(self): self.calls.append(("begin",))
    def capture_time(self): return 99.
    def time_at_capture(self, captured_time): return next(self.times)
    def send_event(self, **kwargs): self.calls.append(("event", kwargs)); return True
    def end_rec(self): self.calls.append(("end",))
    def disconnect(self): self.calls.append(("disconnect",))
    def clock_state(self): return {"ok": True}
    def session_summary(self): return {"ok": True}
    def event_errors(self): return []
    def eci_errors(self): return []


class RejectingStation(FakeStation):
    def send_event(self, **kwargs):
        self.calls.append(("event", kwargs)); return False


class ConnectFailure(FakeStation):
    def connect(self, **kwargs):
        self.calls.append(("connect", kwargs)); raise OSError("offline")


class BeginFailure(FakeStation):
    def begin_rec(self):
        self.calls.append(("begin",)); raise RuntimeError("cannot record")


class DiagnosticFailure(FakeStation):
    def event_errors(self): return [{"message": "ECI error"}]


def transport(station=FakeStation):
    config = Config.load(ROOT / "config.yaml")
    return Transport(config.netstation, station_factory=station,
                     package_report={"class": station, "version": "fake", "source_hashes": {}})


class TransportTests(unittest.TestCase):
    def test_fifo_and_collision_adjustment(self):
        tx = transport(); publisher = Publisher({"run_id": "r", "participant": "001"}, tx)
        publisher.start()
        for event in ("session_start", "experiment_start", "block_start"):
            publisher.publish(publisher.prepare(event), capture_time=99.)
        publisher.checkpoint()
        events = [call[1] for call in tx.station.calls if call[0] == "event"]
        self.assertEqual([x["event_type"] for x in events], ["SESS", "EXPR", "BLST"])
        self.assertEqual([r["transmitted_ms"] for r in publisher.records], [1000, 1001, 1002])
        self.assertEqual([r["adjustment_ms"] for r in publisher.records], [0, 1, 0])
        publisher.close()
        self.assertEqual(tx.recording_state, "stopped")

    def test_positive_ack_required(self):
        tx = transport(RejectingStation); publisher = Publisher({"run_id": "r", "participant": "001"}, tx)
        publisher.start(); publisher.publish(publisher.prepare("session_start"), capture_time=99.)
        with self.assertRaisesRegex(RuntimeError, "send SESS"):
            publisher.checkpoint()
        self.assertEqual(publisher.records[0]["disposition"], "unknown")

    def test_start_and_cleanup_order(self):
        tx = transport(); tx.start(); tx.stop()
        self.assertEqual([x[0] for x in tx.station.calls], ["connect", "begin", "end", "disconnect"])

    def test_connect_failure_still_attempts_disconnect(self):
        tx = transport(ConnectFailure)
        with self.assertRaisesRegex(RuntimeError, "offline"):
            tx.start()
        self.assertEqual([x[0] for x in tx.station.calls], ["connect", "disconnect"])

    def test_begin_failure_attempts_stop_and_disconnect(self):
        tx = transport(BeginFailure)
        with self.assertRaisesRegex(RuntimeError, "cannot record"):
            tx.start()
        self.assertEqual([x[0] for x in tx.station.calls], ["connect", "begin", "end", "disconnect"])

    def test_diagnostics_failure_is_explicit(self):
        tx = transport(DiagnosticFailure)
        with self.assertRaisesRegex(RuntimeError, "diagnostics"):
            tx.start()
        self.assertIn("end", [x[0] for x in tx.station.calls])
        self.assertIn("disconnect", [x[0] for x in tx.station.calls])

    def test_queue_overflow_is_explicit(self):
        config = Config.load(ROOT / "config.yaml")
        small = replace(config.netstation, queue_capacity=1)
        tx = Transport(small, station_factory=FakeStation,
                       package_report={"class": FakeStation, "version": "fake", "source_hashes": {}})
        record = {"disposition": "pending"}
        tx.enqueue(record)
        with self.assertRaisesRegex(RuntimeError, "queue full"):
            tx.enqueue({"disposition": "pending"})
        self.assertEqual(tx.records, [record])


if __name__ == "__main__":
    unittest.main()
