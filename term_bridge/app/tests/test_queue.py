import threading
import time

import pytest

from term_bridge.models import ControllerJob
from term_bridge.queue import ControllerQueue


def make_queue(execute, max_attempts=3, retry_delays=(0.01, 0.01, 0.01)) -> ControllerQueue:
    return ControllerQueue(
        label="test",
        execute=execute,
        command_gap_seconds=0.0,
        max_attempts=max_attempts,
        retry_delays=retry_delays,
    )


def test_enqueue_wait_returns_result_lines():
    def execute(job: ControllerJob) -> None:
        job.result_lines = ["ok"]

    queue = make_queue(execute)
    queue.start()
    try:
        result = queue.enqueue(ControllerJob(kind="temps"), wait=True)
        assert result == ["ok"]
    finally:
        queue.stop(timeout=2)


def test_enqueue_retries_then_succeeds():
    attempts = []

    def execute(job: ControllerJob) -> None:
        attempts.append(1)
        if len(attempts) < 3:
            raise RuntimeError("transient")

    queue = make_queue(execute, max_attempts=5)
    queue.start()
    try:
        queue.enqueue(ControllerJob(kind="regs"), wait=True)
        assert len(attempts) == 3
    finally:
        queue.stop(timeout=2)


def test_enqueue_raises_after_max_attempts():
    def execute(job: ControllerJob) -> None:
        raise RuntimeError("boom")

    queue = make_queue(execute, max_attempts=2, retry_delays=(0.01,))
    queue.start()
    try:
        with pytest.raises(RuntimeError, match="boom"):
            queue.enqueue(ControllerJob(kind="regs"), wait=True)
    finally:
        queue.stop(timeout=2)


def test_retry_with_empty_delay_sequence_does_not_crash():
    attempts = 0

    def execute(job: ControllerJob) -> None:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("transient")

    queue = make_queue(execute, max_attempts=2, retry_delays=())
    queue.start()
    try:
        queue.enqueue(ControllerJob(kind="regs"), wait=True)
        assert attempts == 2
    finally:
        queue.stop(timeout=2)


def test_is_kind_active_or_queued_reflects_pending_jobs():
    started = threading.Event()
    release = threading.Event()

    def execute(job: ControllerJob) -> None:
        started.set()
        release.wait(timeout=2)

    queue = make_queue(execute)
    queue.start()
    try:
        queue.enqueue(ControllerJob(kind="set", zone_unique_id="z1"), wait=False)
        assert started.wait(timeout=2)
        assert queue.is_kind_active_or_queued("set") is True
        assert queue.is_kind_active_or_queued("temps") is False
    finally:
        release.set()
        queue.stop(timeout=2)


def test_command_gap_is_enforced_between_jobs():
    timestamps = []

    def execute(job: ControllerJob) -> None:
        timestamps.append(time.monotonic())

    queue = ControllerQueue(
        label="gap-test",
        execute=execute,
        command_gap_seconds=0.2,
        max_attempts=1,
        retry_delays=(),
    )
    queue.start()
    try:
        queue.enqueue(ControllerJob(kind="temps"), wait=True)
        queue.enqueue(ControllerJob(kind="temps"), wait=True)
        assert timestamps[1] - timestamps[0] >= 0.2
    finally:
        queue.stop(timeout=2)


def test_stop_unblocks_waiting_pending_job():
    active_started = threading.Event()
    release_active = threading.Event()

    def execute(job: ControllerJob) -> None:
        active_started.set()
        release_active.wait(timeout=2)

    queue = make_queue(execute)
    queue.start()
    queue.enqueue(ControllerJob(kind="temps"), wait=False)
    assert active_started.wait(timeout=2)

    pending = ControllerJob(kind="regs")
    waiter_error: list[BaseException] = []

    def wait_for_pending() -> None:
        try:
            queue.enqueue(pending, wait=True)
        except BaseException as exc:  # test captures the worker-facing failure
            waiter_error.append(exc)

    waiter = threading.Thread(target=wait_for_pending)
    waiter.start()
    time.sleep(0.05)
    queue.stop(timeout=0.05)

    waiter.join(timeout=1)
    release_active.set()
    queue.stop(timeout=2)

    assert not waiter.is_alive()
    assert waiter_error
    assert "stopped before job execution" in str(waiter_error[0])


def test_queue_can_be_started_again_after_clean_stop():
    executions = 0

    def execute(job: ControllerJob) -> None:
        nonlocal executions
        executions += 1

    queue = make_queue(execute)
    queue.start()
    queue.enqueue(ControllerJob(kind="temps"), wait=True)
    queue.stop(timeout=2)

    with pytest.raises(RuntimeError, match="is stopped"):
        queue.enqueue(ControllerJob(kind="temps"), wait=False)

    queue.start()
    try:
        queue.enqueue(ControllerJob(kind="temps"), wait=True)
    finally:
        queue.stop(timeout=2)

    assert executions == 2


def test_invalid_queue_configuration_is_rejected():
    with pytest.raises(ValueError, match="max_attempts"):
        make_queue(lambda job: None, max_attempts=0)

    with pytest.raises(ValueError, match="negative"):
        ControllerQueue(
            label="bad-gap",
            execute=lambda job: None,
            command_gap_seconds=-1,
            max_attempts=1,
            retry_delays=(),
        )


def test_completion_callback_receives_success_and_failure():
    completions = []

    def on_complete(job, error):
        completions.append((job.kind, error))

    attempts = 0

    def execute(job):
        nonlocal attempts
        attempts += 1
        if job.kind == "regs":
            raise RuntimeError("offline")

    queue = ControllerQueue(
        label="callback-test",
        execute=execute,
        command_gap_seconds=0,
        max_attempts=1,
        retry_delays=(),
        on_complete=on_complete,
    )
    queue.start()
    try:
        queue.enqueue(ControllerJob(kind="temps"), wait=True)
        with pytest.raises(RuntimeError, match="offline"):
            queue.enqueue(ControllerJob(kind="regs"), wait=True)
    finally:
        queue.stop(timeout=2)

    assert completions[0] == ("temps", None)
    assert completions[1][0] == "regs"
    assert isinstance(completions[1][1], RuntimeError)
