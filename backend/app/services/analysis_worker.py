"""In-process pool that analyzes different patient images at the same time.

One dispatcher claims jobs. Daemon workers, sized by QUEUE_CONCURRENCY, run the
AI calls. Idle workers wait on an in-memory queue, so they do not poll the database.
"""

from __future__ import annotations

import os
import queue
import threading

from flask import Flask

from app.extensions import db
from app.services.queue_service import claim_for_worker, execute_claimed


class AnalysisQueueWorker:
    def __init__(self, app: Flask):
        self.app = app
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._jobs: queue.Queue[tuple[int, int, int] | None] = queue.Queue()
        self._slots: threading.Semaphore | None = None
        self._threads: list[threading.Thread] = []

    def wake(self) -> None:
        """Start a waiting image immediately. No poll interval before it runs."""
        self._wake.set()

    def start(self) -> None:
        if any(thread.is_alive() for thread in self._threads):
            return
        self._stop.clear()
        count = int(self.app.config.get("QUEUE_CONCURRENCY", 1))
        self._slots = threading.Semaphore(count)
        self._jobs = queue.Queue()
        self._threads = []
        dispatch = threading.Thread(
            target=self._dispatch_loop,
            name="via-analysis-dispatch",
            daemon=True,
        )
        dispatch.start()
        self._threads.append(dispatch)
        for index in range(count):
            worker = threading.Thread(
                target=self._run_loop,
                name=f"via-analysis-{index + 1}",
                daemon=True,
            )
            worker.start()
            self._threads.append(worker)
        self.app.logger.info("VIA analysis pool started with %s workers", count)

    def stop(self, timeout: float = 2.0) -> None:
        self._stop.set()
        self._wake.set()
        count = sum(1 for thread in self._threads if thread.name.startswith("via-analysis-"))
        # The dispatcher thread is included in that count. One sentinel per worker
        # is enough; extra sentinels are harmless.
        for _ in range(max(count, 1)):
            self._jobs.put(None)
        for thread in list(self._threads):
            if thread is not threading.current_thread():
                thread.join(timeout=timeout)

    def _dispatch_loop(self) -> None:
        while not self._stop.is_set():
            slots = self._slots
            if slots is None or not slots.acquire(timeout=self.app.config["QUEUE_POLL_SECONDS"]):
                continue
            if self._stop.is_set():
                slots.release()
                return

            claimed = None
            try:
                with self.app.app_context():
                    try:
                        claimed = claim_for_worker()
                    except Exception:
                        db.session.rollback()
                        raise
            except Exception:
                slots.release()
                self.app.logger.exception("VIA analysis queue worker error")
                continue

            if claimed is None:
                slots.release()
                self._wake.wait(self.app.config["QUEUE_POLL_SECONDS"])
                self._wake.clear()
                continue

            self._jobs.put(claimed)

    def _run_loop(self) -> None:
        while not self._stop.is_set():
            try:
                claimed = self._jobs.get(timeout=self.app.config["QUEUE_POLL_SECONDS"])
            except queue.Empty:
                continue
            if claimed is None:
                return
            try:
                with self.app.app_context():
                    try:
                        execute_claimed(claimed)
                    except Exception:
                        db.session.rollback()
                        self.app.logger.exception("VIA analysis queue worker error")
            finally:
                if self._slots is not None:
                    self._slots.release()
                self._wake.set()


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
