"""Runs a function every N seconds on a daemon thread (used for the SLA scan)."""
import logging, threading

class PeriodicTask:
    def __init__(self, fn, interval_seconds: float, name="task"):
        self._fn, self._interval, self._name = fn, interval_seconds, name
        self._stop = threading.Event(); self._thread = threading.Thread(target=self._run, name=name, daemon=True)
    def start(self): self._thread.start()
    def stop(self): self._stop.set()
    def _run(self):
        while not self._stop.wait(self._interval):
            try: self._fn()
            except NotImplementedError: logging.warning("%s is not implemented yet; stopping this task", self._name); return
            except Exception: logging.exception("%s failed; will retry", self._name)   # a failed run must not kill the loop
