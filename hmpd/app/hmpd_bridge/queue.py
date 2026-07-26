"""Per-controller serial FIFO with retry/backoff and safe lifecycle handling.

Serial controllers can only handle one command at a time, so each controller gets its
own queue and worker thread. The queue itself does not know what a job means; it calls
the supplied ``execute`` callback and handles pacing, retries, shutdown, and worker
restarts.
"""
from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable, Sequence

from .models import ControllerJob

log = logging.getLogger("hmpd_bridge.queue")


class ControllerQueue:
    def __init__(
        self,
        label: str,
        execute: Callable[[ControllerJob], None],
        *,
        command_gap_seconds: float,
        max_attempts: int,
        retry_delays: Sequence[float],
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if command_gap_seconds < 0:
            raise ValueError("command_gap_seconds must not be negative")
        if any(delay < 0 for delay in retry_delays):
            raise ValueError("retry delays must not be negative")

        self.label = label
        self._execute = execute
        self.command_gap_seconds = command_gap_seconds
        self.max_attempts = max_attempts
        self.retry_delays = list(retry_delays)

        self._condition = threading.Condition()
        self._items: list[ControllerJob] = []
        self._shutdown = threading.Event()
        self._thread: threading.Thread | None = None
        self._current_kind: str | None = None
        self._last_finished_at = 0.0

    def start(self) -> None:
        with self._condition:
            if self._thread is not None and self._thread.is_alive():
                return
            self._shutdown.clear()
            self._thread = threading.Thread(
                target=self._worker_loop,
                name=f"hmpd_worker_{self.label}",
                daemon=False,
            )
            self._thread.start()

    def is_alive(self) -> bool:
        with self._condition:
            return self._thread is not None and self._thread.is_alive()

    def restart_if_dead(self) -> None:
        with self._condition:
            should_restart = self._thread is not None and not self._thread.is_alive() and not self._shutdown.is_set()
        if should_restart:
            log.critical("Worker thread for %s is dead, restarting", self.label)
            self.start()

    def stop(self, timeout: float = 10.0) -> None:
        shutdown_error = RuntimeError(f"Controller queue {self.label} stopped before job execution")
        with self._condition:
            self._shutdown.set()
            pending, self._items = self._items, []
            for job in pending:
                if job.error is None:
                    job.error = shutdown_error
                job.done.set()
            self._condition.notify_all()
            thread = self._thread

        if thread is not None:
            thread.join(timeout=timeout)
            if thread.is_alive():
                log.warning("Worker thread %s did not exit cleanly", self.label)

    def enqueue(self, job: ControllerJob, wait: bool = False) -> list[str]:
        with self._condition:
            if self._shutdown.is_set():
                raise RuntimeError(f"Cannot enqueue job: controller queue {self.label} is stopped")
            self._items.append(job)
            queue_len = len(self._items)
            self._condition.notify()
        log.debug("Enqueued %s for %s reason=%s queue_len=%s", job.kind, self.label, job.reason or "-", queue_len)

        if not wait:
            return []

        job.done.wait()
        if job.error is not None:
            raise job.error
        return job.result_lines

    def pending_set_count(self) -> int:
        with self._condition:
            return sum(1 for job in self._items if job.kind == "set")

    def is_kind_active_or_queued(self, kind: str) -> bool:
        with self._condition:
            return self._current_kind == kind or any(job.kind == kind for job in self._items)

    def _worker_loop(self) -> None:
        while True:
            try:
                with self._condition:
                    while not self._items and not self._shutdown.is_set():
                        self._condition.wait(timeout=1.0)
                    if self._shutdown.is_set():
                        break
                    job = self._items.pop(0)
                    self._current_kind = job.kind

                try:
                    self._execute_with_retries(job)
                except Exception as exc:  # noqa: BLE001 - job failure is reported via job.error
                    job.error = exc
                    log.error(
                        "Queue job failed permanently kind=%s controller=%s reason=%s err=%s",
                        job.kind,
                        self.label,
                        job.reason or "-",
                        exc,
                        exc_info=True,
                    )
                finally:
                    with self._condition:
                        self._last_finished_at = time.monotonic()
                        self._current_kind = None
                    job.done.set()
            except Exception:  # noqa: BLE001 - never let the worker thread die silently
                log.critical("Unhandled exception in controller worker %s", self.label, exc_info=True)
                if self._shutdown.wait(timeout=5.0):
                    break
        log.info("Controller worker loop exiting for %s", self.label)

    def _enforce_command_gap(self) -> None:
        with self._condition:
            last_finished_at = self._last_finished_at
        remaining = self.command_gap_seconds - (time.monotonic() - last_finished_at)
        if remaining > 0:
            self._shutdown.wait(timeout=remaining)

    def _retry_delay(self, attempt: int) -> float:
        if not self.retry_delays:
            return 0.0
        return self.retry_delays[min(attempt - 1, len(self.retry_delays) - 1)]

    def _execute_with_retries(self, job: ControllerJob) -> None:
        last_exc: BaseException | None = None

        for attempt in range(1, self.max_attempts + 1):
            if self._shutdown.is_set():
                raise RuntimeError(f"Controller queue {self.label} stopped during job execution")
            try:
                self._enforce_command_gap()
                if self._shutdown.is_set():
                    raise RuntimeError(f"Controller queue {self.label} stopped during job execution")
                self._execute(job)
                return
            except Exception as exc:  # noqa: BLE001 - retried below, re-raised after last attempt
                last_exc = exc
                if attempt >= self.max_attempts or self._shutdown.is_set():
                    break
                delay = self._retry_delay(attempt)
                log.warning(
                    "Command failed attempt %s/%s for %s kind=%s reason=%s: %s. Retrying in %ss",
                    attempt,
                    self.max_attempts,
                    self.label,
                    job.kind,
                    job.reason or "-",
                    exc,
                    delay,
                )
                if self._shutdown.wait(timeout=delay):
                    break

        log.critical(
            "Command failed after %s attempts for %s kind=%s reason=%s action=%s last_error=%s",
            self.max_attempts,
            self.label,
            job.kind,
            job.reason or "-",
            job.action_args,
            last_exc,
        )
        raise RuntimeError(
            f"Command failed after {self.max_attempts} attempts for {self.label} "
            f"kind={job.kind} reason={job.reason or '-'}: {last_exc}"
        )
