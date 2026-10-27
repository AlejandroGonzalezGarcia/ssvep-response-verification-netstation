"""Bounded, serial NetStation 2.1.0 transport. Imported only in netstation mode."""
from __future__ import annotations

import hashlib
import importlib.metadata
import inspect
import math
from pathlib import Path
import queue
import threading
import time


EXPECTED_VERSION = "2.1.0"
EXPECTED_HASHES = {
    "NetStation.py": "1e64ef41544db4a45deebffabe3b1e85f2dd61048534c173875da19d593568f8",
    "__init__.py": "6b65ddb0104dbb0d031f5251f5e7944c1939502b7668767f44958d611226d7fa",
    "eci.py": "32da0eea162020bffe6bb895951fd7ecfc60cbcb7e1fa76562f7cc7ae69fcea3",
    "egi_ntp.py": "e3944da98b5cc47a370921f96d8f54e443b643ce37ea7068006ca21d4075af07",
    "exceptions.py": "ac61fb519e3a47f5f1b0a3c62e40f9bbfc65c4ee0a78891e7387821d184dab3a",
    "socket_wrapper.py": "3c9179e4e3b06e5dc2e77a575ef4a799b025e696d6bd6cb12fcba4581f246170",
    "util.py": "a6813a29a49f10162320a066374cc1405b6a92752196fa1e02a10968a705a676",
}


def inspect_package():
    version = importlib.metadata.version("egi-pynetstation")
    if version != EXPECTED_VERSION:
        raise RuntimeError(f"egi-pynetstation {EXPECTED_VERSION} required; found {version}")
    from egi_pynetstation.NetStation import NetStation
    root = Path(inspect.getfile(NetStation)).parent
    hashes = {}
    for name, expected in EXPECTED_HASHES.items():
        path = root / name
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        hashes[name] = actual
        if actual != expected:
            raise RuntimeError(f"egi-pynetstation source mismatch for {name}: {actual}")
    required = {
        "connect": ("ntp_ip", "strict_eci"), "begin_rec": (), "capture_time": (),
        "time_at_capture": ("captured_time",), "send_event": ("start", "duration", "event_type", "label", "desc", "data", "wait"),
        "clock_state": (), "session_summary": (), "event_errors": (), "eci_errors": (),
        "end_rec": (), "disconnect": (),
    }
    for method, names in required.items():
        if not hasattr(NetStation, method):
            raise RuntimeError(f"egi-pynetstation missing NetStation.{method}")
        params = inspect.signature(getattr(NetStation, method)).parameters
        for name in names:
            if name not in params:
                raise RuntimeError(f"NetStation.{method} missing {name} parameter")
    return {"version": version, "module_root": str(root), "source_hashes": hashes, "class": NetStation}


class Transport:
    def __init__(self, config, station_factory=None, package_report=None):
        self.config = config
        report = package_report or inspect_package()
        self.package_report = {k: v for k, v in report.items() if k != "class"}
        factory = station_factory or report["class"]
        self.station = factory(config.eci_ip, config.port)
        self.queue = queue.Queue(maxsize=config.queue_capacity)
        self.thread = None
        self.failure = None
        self.previous_ms = -1
        self.recording_state = "not_started"
        self.connection_attempted = False
        self.recording_attempted = False
        self.cleanup_errors = []
        self.diagnostics = []
        self.records = []

    def start(self):
        try:
            self.connection_attempted = True
            self.station.connect(ntp_ip=self.config.ntp_ip, strict_eci=True)
            self.recording_state = "connected"
            self.recording_attempted = True
            self.station.begin_rec()
            self.recording_state = "recording"
            self._inspect_diagnostics("recording_started", strict=True)
        except BaseException as exc:
            self.failure = RuntimeError(self._message("start", exc))
            self._cleanup()
            raise self.failure
        self.thread = threading.Thread(target=self._worker, name="netstation-eci", daemon=True)
        self.thread.start()

    def capture_time(self):
        return self.station.capture_time()

    def enqueue(self, record):
        self.check()
        try:
            self.queue.put_nowait(("event", record))
            self.records.append(record)
        except queue.Full as exc:
            record["disposition"] = "not_sent"
            self.failure = RuntimeError(self._message("enqueue (queue full)", exc))
            raise self.failure

    def _worker(self):
        while True:
            kind, item = self.queue.get()
            try:
                if kind == "stop":
                    item.set()
                    return
                if kind == "barrier":
                    item.set()
                    continue
                if self.failure is not None:
                    item["disposition"] = "not_sent"
                    item["error"] = "Transport had already failed before this event was sent"
                    continue
                self._send(item)
            except BaseException as exc:
                item["disposition"] = "unknown" if item.get("send_started_monotonic") else "not_sent"
                item["error"] = f"{type(exc).__name__}: {exc}"
                self.failure = self.failure or RuntimeError(self._message(f"send {item.get('code')}", exc))
            finally:
                self.queue.task_done()

    def _send(self, record):
        natural = float(self.station.time_at_capture(captured_time=record["capture_time"]))
        if not math.isfinite(natural) or natural < 0:
            raise ValueError(f"invalid converted EGI time {natural}")
        natural_ms = int(natural * 1000)
        transmitted_ms = max(natural_ms, self.previous_ms + 1)
        if not 0 <= transmitted_ms <= 2147483647:
            raise ValueError("converted EGI milliseconds outside signed 32-bit range")
        start = transmitted_ms / 1000
        if int(start * 1000) != transmitted_ms:
            start = math.nextafter(start, math.inf)
        self.previous_ms = transmitted_ms
        record.update(natural_start_s=natural, natural_ms=natural_ms, transmitted_ms=transmitted_ms,
                      adjustment_ms=transmitted_ms-natural_ms, netstation_start_s=start,
                      send_started_monotonic=time.monotonic())
        response = self.station.send_event(start=start, duration=.001, event_type=record["code"],
                                           label=record["code"], desc=record["semantic_event"],
                                           data=record["metadata"], wait=True)
        record["response_monotonic"] = time.monotonic()
        if response is not True:
            raise RuntimeError(f"NetStation did not positively acknowledge event: {response!r}")
        record["disposition"] = "acknowledged"

    def check(self):
        if self.failure:
            raise self.failure

    def checkpoint(self):
        self.check()
        barrier = threading.Event()
        self.queue.put(("barrier", barrier), timeout=self.config.operation_timeout_s)
        if not barrier.wait(self.config.operation_timeout_s):
            raise RuntimeError(self._message("checkpoint", TimeoutError("worker timeout")))
        self.check()
        self._inspect_diagnostics("checkpoint", strict=True)

    def stop(self):
        if self.thread and self.thread.is_alive():
            stop = threading.Event()
            try:
                self.queue.put(("stop", stop), timeout=self.config.operation_timeout_s)
                if not stop.wait(self.config.operation_timeout_s):
                    raise TimeoutError("worker shutdown timeout")
                self.thread.join(self.config.operation_timeout_s)
            except BaseException as exc:
                self.cleanup_errors.append(self._message("drain", exc) +
                                           "; recording state may be unknown; check and stop NetStation manually")
                self.recording_state = "unknown"
                for record in self.records:
                    if record.get("disposition") == "pending":
                        record["disposition"] = "unknown" if record.get("send_started_monotonic") else "not_sent"
                        record["error"] = self.cleanup_errors[-1]
        self._cleanup()
        self.check()

    def _cleanup(self):
        if self.recording_attempted and self.recording_state not in {"stopped", "not_started"}:
            try:
                self._inspect_diagnostics("before_stop", strict=False)
                self.station.end_rec()
                self.recording_state = "stopped"
                self._inspect_diagnostics("after_stop", strict=False)
            except BaseException as exc:
                self.cleanup_errors.append(self._message("end recording", exc))
                self.recording_state = "unknown"
        if self.connection_attempted:
            try:
                self.station.disconnect()
            except BaseException as exc:
                self.cleanup_errors.append(self._message("disconnect", exc))

    def _message(self, operation, exc):
        detail = getattr(exc, "message", str(exc))
        return (f"NetStation {operation} failed for ECI {self.config.eci_ip}:{self.config.port}, "
                f"NTP {self.config.ntp_ip}: {type(exc).__name__}: {detail}")

    def _inspect_diagnostics(self, stage, strict):
        snapshot = {"stage": stage, "monotonic": time.monotonic()}
        for name in ("clock_state", "session_summary", "event_errors", "eci_errors"):
            method = getattr(self.station, name, None)
            if method is not None:
                try:
                    snapshot[name] = method()
                except BaseException as exc:
                    snapshot[name] = {"error": f"{type(exc).__name__}: {exc}"}
        self.diagnostics.append(snapshot)
        errors = snapshot.get("event_errors") or snapshot.get("eci_errors")
        if strict and errors:
            raise RuntimeError(f"NetStation diagnostics reported errors at {stage}: {errors}")

    def snapshot(self):
        return {"package": self.package_report, "recording_state": self.recording_state,
                "connection_attempted": self.connection_attempted, "recording_attempted": self.recording_attempted,
                "failure": None if self.failure is None else str(self.failure),
                "cleanup_errors": list(self.cleanup_errors), "diagnostics": list(self.diagnostics)}
