"""In-process pool that analyzes different patient images at the same time."""

from __future__ import annotations

import os
import threading

from flask import Flask

from app.extensions import db
from app.services.queue_service import process_next


class AnalysisQueueWorker:
    def __init__(self, app: Flask):
        self.app = app
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._threads: list[threading.Thread] = []

    def wake(self) -> None:
        """Start a waiting image immediately. No poll interval before it runs."""
        self._wake.set()

    def start(self) -> None:
        if any(thread.is_alive() for thread in self._threads):
            return
        self._stop.clear()
        count = int(self.app.config.get("QUEUE_CONCURRENCY", 1))
        self._threads = []
        for index in range(count):
            thread = threading.Thread(
                target=self._loop,
                name=f"via-analysis-{index + 1}",
                daemon=True,
            )
            thread.start()
            self._threads.append(thread)
        self.app.logger.info("VIA analysis pool started with %s workers", count)

    def stop(self, timeout: float = 2.0) -> None:
        self._stop.set()
        self._wake.set()
        for thread in list(self._threads):
            if thread is not threading.current_thread():
                thread.join(timeout=timeout)

    def _loop(self) -> None:
        while not self._stop.is_set():
            worked = False
            try:
                with self.app.app_context():
                    try:
                        worked = process_next()
                    except Exception:
                        db.session.rollback()
                        raise
            except Exception:
                self.app.logger.exception("VIA analysis queue worker error")
                try:
                    with self.app.app_context():
                        db.session.rollback()
                except Exception:
                    self.app.logger.exception("failed to roll back analysis queue session")
            if worked:
                continue
            # Idle only. A new upload sets _wake and this returns at once.
            self._wake.wait(self.app.config["QUEUE_POLL_SECONDS"])
            self._wake.clear()
            if self._stop.is_set():
                return


def wake_analysis_worker() -> None:
    from flask import current_app

    worker = current_app.extensions.get("analysis_worker")
    if isinstance(worker, AnalysisQueueWorker):
        worker.wake()


def start_analysis_worker(app: Flask) -> AnalysisQueueWorker:
    worker = app.extensions.get("analysis_worker")
    if not isinstance(worker, AnalysisQueueWorker):
        worker = AnalysisQueueWorker(app)
        app.extensions["analysis_worker"] = worker
    worker.start()
    return worker


def stop_analysis_worker(app: Flask) -> None:
    worker = app.extensions.get("analysis_worker")
    if isinstance(worker, AnalysisQueueWorker):
        worker.stop()


def maybe_start_analysis_worker(app: Flask) -> None:
    if not app.config.get("QUEUE_WORKER_ENABLED", True):
        return
    # The Werkzeug reloader imports the app in the parent process. Only the
    # child that serves requests should own the worker.
    if app.debug and os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        return
    start_analysis_worker(app)
