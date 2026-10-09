# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import asyncio
import threading
from datetime import timedelta
from queue import Queue
from types import SimpleNamespace

import pytest
from pytest_simcore.helpers.xdist import (
    ReaderWriterLock,
    SharedResourceRegistry,
    ashared_resource_session,
    daemon_churn_access,
    shared_resource_session,
)


class _SetupBoomError(RuntimeError):
    pass


class _BodyBoomError(RuntimeError):
    pass


class _TeardownBoomError(RuntimeError):
    pass


@pytest.fixture
def xdist_master_request():
    """a non-xdist (`master`) request: the session must degenerate to plain setup/teardown"""
    return SimpleNamespace(config=SimpleNamespace(workerinput=None))


def test_session_runs_setup_and_teardown_once_without_xdist(xdist_master_request, tmp_path_factory):
    calls: list[str] = []

    with shared_resource_session(
        xdist_master_request,
        tmp_path_factory,
        "test_resource",
        setup_fn=lambda: calls.append("setup"),
        teardown_fn=lambda: calls.append("teardown"),
    ) as owns_setup:
        assert owns_setup is True
        assert calls == ["setup"]
        calls.append("body")

    assert calls == ["setup", "body", "teardown"]


def test_session_setup_failure_skips_body_and_still_teardowns(xdist_master_request, tmp_path_factory):
    calls: list[str] = []

    def _setup_boom() -> None:
        calls.append("setup")
        raise _SetupBoomError

    with (
        pytest.raises(_SetupBoomError),
        shared_resource_session(
            xdist_master_request,
            tmp_path_factory,
            "test_resource",
            setup_fn=_setup_boom,
            teardown_fn=lambda: calls.append("teardown"),
        ),
    ):
        calls.append("body")  # must never run

    assert calls == ["setup", "teardown"]


def test_session_body_failure_propagates_and_teardowns(xdist_master_request, tmp_path_factory):
    calls: list[str] = []

    with (
        pytest.raises(_BodyBoomError),
        shared_resource_session(
            xdist_master_request,
            tmp_path_factory,
            "test_resource",
            setup_fn=lambda: calls.append("setup"),
            teardown_fn=lambda: calls.append("teardown"),
        ),
    ):
        raise _BodyBoomError

    assert calls == ["setup", "teardown"]


def test_session_teardown_errors_propagate(xdist_master_request, tmp_path_factory):
    def _teardown_boom() -> None:
        raise _TeardownBoomError

    with (
        pytest.raises(_TeardownBoomError),
        shared_resource_session(
            xdist_master_request,
            tmp_path_factory,
            "test_resource",
            setup_fn=lambda: None,
            teardown_fn=_teardown_boom,
        ),
    ):
        pass


def test_churn_access_is_noop_without_xdist(xdist_master_request, tmp_path_factory):
    with daemon_churn_access(xdist_master_request, tmp_path_factory):
        pass  # must not touch any lock marker outside xdist


def test_session_waits_with_registry_under_xdist(monkeypatch: pytest.MonkeyPatch, tmp_path_factory):
    """emulates a worker that is NOT the setup owner: it must wait for readiness, skip the
    setup, and NOT run the teardown when other users remain registered
    """
    worker_request = SimpleNamespace(config=SimpleNamespace(workerinput={"workerid": "gw0"}))
    calls: list[str] = []

    class _FakeRegistry:
        def __init__(self, _root, _name) -> None:
            self.unregistered: list[str] = []

        @staticmethod
        def register(_token: str) -> bool:
            return False  # someone else owns the setup

        @staticmethod
        def wait_ready(*, timeout: timedelta) -> None:
            assert timeout > timedelta(0)

        def unregister(self, token: str) -> bool:
            self.unregistered.append(token)
            return False  # other users remain: no teardown here

    created: list[_FakeRegistry] = []

    def _fake_registry_cls(root, name) -> _FakeRegistry:
        reg = _FakeRegistry(root, name)
        created.append(reg)
        return reg

    monkeypatch.setattr("pytest_simcore.helpers.xdist.SharedResourceRegistry", _fake_registry_cls)

    with shared_resource_session(
        worker_request,
        tmp_path_factory,
        "test_resource",
        setup_fn=lambda: calls.append("setup"),
        teardown_fn=lambda: calls.append("teardown"),
        wait_timeout=timedelta(seconds=1),
    ) as owns_setup:
        assert owns_setup is False
        assert calls == []  # waiter skipped the real setup

    assert calls == []
    assert len(created) == 1
    assert len(created[0].unregistered) == 1  # token given back exactly once


def _worker_request(workerid: str):
    return SimpleNamespace(config=SimpleNamespace(workerinput={"workerid": workerid}))


def _isolate_root(monkeypatch: pytest.MonkeyPatch, tmp_path_factory, name: str):
    """point the sessions at a per-test root dir: the real one is shared by every test in the
    run and markers/tokens from one test would fence the next
    """
    root = tmp_path_factory.mktemp(name)
    monkeypatch.setattr("pytest_simcore.helpers.xdist.get_xdist_root_tmp_path", lambda _tf: root)
    return root


def test_next_generation_setup_waits_while_previous_teardown_in_progress(
    monkeypatch: pytest.MonkeyPatch, tmp_path_factory
):
    """the last holder's teardown must stay visible (registry generation marker) so a fresh
    setup-owner cannot run its `setup_fn` concurrently with the destructive cleanup it replaced
    """
    _isolate_root(monkeypatch, tmp_path_factory, "overlap")
    calls: list[str] = []
    teardown_started = threading.Event()
    release_teardown = threading.Event()
    errors: Queue[BaseException] = Queue()

    def _blocked_teardown() -> None:
        calls.append("teardown:started")
        teardown_started.set()
        assert release_teardown.wait(timeout=10), "test must release the teardown"
        calls.append("teardown:done")

    def _session(workerid: str, setup_marker: str) -> None:
        try:
            with shared_resource_session(
                _worker_request(workerid),
                tmp_path_factory,
                "test_resource",
                setup_fn=lambda: calls.append(setup_marker),
                teardown_fn=_blocked_teardown if workerid == "gw0" else lambda: calls.append(f"teardown:{workerid}"),
                wait_timeout=timedelta(seconds=10),
            ):
                pass
        except BaseException as exc:  # pylint: disable=broad-exception-caught
            errors.put(exc)  # the thread must fail the test, not raise in a foreign stack

    first_generation = threading.Thread(target=_session, args=("gw0", "setup1"))
    first_generation.start()
    assert teardown_started.wait(timeout=10), "first session never started tearing down"

    # while that generation's teardown is still in flight, a fresh session must block
    second_generation = threading.Thread(target=_session, args=("gw1", "setup2"))
    second_generation.start()
    second_generation.join(timeout=1)
    assert second_generation.is_alive()  # still blocked: NOT started over the in-flight teardown
    assert "setup2" not in calls

    release_teardown.set()
    first_generation.join(timeout=10)
    second_generation.join(timeout=10)
    assert errors.empty(), errors.get_nowait()
    assert calls == ["setup1", "teardown:started", "teardown:done", "setup2", "teardown:gw1"]


def test_stale_teardown_marker_blocks_until_manually_removed(tmp_path_factory):
    """a marker surviving the full wait does NOT prove its holder died (a slow teardown can
    outlive any fixed budget), so the wait must fail hard rather than clear it: recovery is
    explicit (`end_teardown` here stands for the operator removing the marker after checking)
    """
    root = tmp_path_factory.mktemp("stale_teardown")
    registry = SharedResourceRegistry(root, "test_resource")
    registry.register("dead-worker")
    assert registry.unregister("dead-worker")  # publishes the teardown marker
    with pytest.raises(TimeoutError):  # in-flight: a waiter cannot get through
        registry.wait_teardown_done(timeout=timedelta(milliseconds=1))
    registry2 = SharedResourceRegistry(root, "test_resource")
    assert registry2.register("new-owner")  # registering does NOT clear the (possibly live) marker
    with pytest.raises(TimeoutError):
        registry2.wait_teardown_done(timeout=timedelta(milliseconds=1))
    assert registry2._teardown_marker.exists()  # noqa: SLF001  # fail-hard: the timeout did NOT clear it
    registry2.end_teardown()  # explicit recovery (operator verified/removes the marker)
    registry2.wait_teardown_done(timeout=timedelta(seconds=1))  # next owner proceeds


def test_failed_teardown_keeps_marker_for_manual_recovery(monkeypatch: pytest.MonkeyPatch, tmp_path_factory):
    """when the last holder's teardown raises, the resource is only half-removed: the marker
    must stay so the next generation refuses to set up over it
    """
    root = _isolate_root(monkeypatch, tmp_path_factory, "teardown_boom")

    def _teardown_boom() -> None:
        raise _TeardownBoomError

    with (
        pytest.raises(_TeardownBoomError),
        shared_resource_session(
            _worker_request("gw0"),
            tmp_path_factory,
            "test_resource",
            setup_fn=lambda: None,
            teardown_fn=_teardown_boom,
        ),
    ):
        pass
    registry = SharedResourceRegistry(root, "test_resource")
    assert registry._teardown_marker.exists()  # noqa: SLF001  # still fenced for the operator to recover


def test_owner_setup_failure_as_last_user_clears_marker_after_cleanup(
    monkeypatch: pytest.MonkeyPatch, tmp_path_factory
):
    """the failure cleanup of the LAST registered holder must end the teardown generation it
    published via `unregister`, else the next session waits the full timeout on a finished cleanup
    """
    root = _isolate_root(monkeypatch, tmp_path_factory, "setup_fail_last")
    calls: list[str] = []

    def _setup_boom() -> None:
        calls.append("setup")
        raise _SetupBoomError

    with (
        pytest.raises(_SetupBoomError),
        shared_resource_session(
            _worker_request("gw0"),
            tmp_path_factory,
            "test_resource",
            setup_fn=_setup_boom,
            teardown_fn=lambda: calls.append("teardown"),
            setup_failed_cleanup_fn=lambda: calls.append("cleanup"),
        ),
    ):
        pass

    assert calls == ["setup", "cleanup"]
    registry = SharedResourceRegistry(root, "test_resource")
    assert not registry._teardown_marker.exists()  # noqa: SLF001  # cleanup completed: generation ended
    registry.wait_teardown_done(timeout=timedelta(seconds=1))  # next owner proceeds at once


def test_owner_setup_failure_defers_cleanup_to_registered_waiters(monkeypatch: pytest.MonkeyPatch, tmp_path_factory):
    """an owner that fails while other users are still registered must NOT run the cleanup
    itself (it would tear the resource down under them): the last waiter to leave owns it
    """
    worker_request = _worker_request("gw0")
    calls: list[str] = []

    class _FakeRegistry:
        def __init__(self, _root, _name) -> None:
            self.unregistered: list[str] = []

        @staticmethod
        def register(_token: str) -> bool:
            return True  # this process owns the setup

        @staticmethod
        def wait_teardown_done(*, timeout: timedelta) -> None:
            assert timeout > timedelta(0)

        @staticmethod
        def mark_failed() -> None:
            pass

        def unregister(self, token: str) -> bool:
            self.unregistered.append(token)
            return False  # waiters are still registered: they own the cleanup

    monkeypatch.setattr("pytest_simcore.helpers.xdist.SharedResourceRegistry", _FakeRegistry)

    def _setup_boom() -> None:
        raise _SetupBoomError

    with (
        pytest.raises(_SetupBoomError),
        shared_resource_session(
            worker_request,
            tmp_path_factory,
            "test_resource",
            setup_fn=_setup_boom,
            teardown_fn=lambda: calls.append("teardown"),
            setup_failed_cleanup_fn=lambda: calls.append("cleanup"),
        ),
    ):
        pass

    assert calls == []  # NO premature cleanup while waiters hold tokens


@pytest.mark.asyncio
async def test_ashared_session_runs_async_setup_and_teardown(xdist_master_request, tmp_path_factory):
    calls: list[str] = []

    async def _async_setup() -> None:
        await _tick()
        calls.append("setup")

    async def _tick() -> None:
        await asyncio.sleep(0)

    async with ashared_resource_session(
        xdist_master_request,
        tmp_path_factory,
        "test_resource",
        setup_fn=_async_setup,
        teardown_fn=lambda: calls.append("teardown"),
    ) as owns_setup:
        assert owns_setup is True
        assert calls == ["setup"]
        calls.append("body")

    assert calls == ["setup", "body", "teardown"]


@pytest.mark.asyncio
async def test_ashared_session_accepts_sync_setup_callback(xdist_master_request, tmp_path_factory):
    """the signature allows a sync callback returning None: it must run, not TypeError"""
    calls: list[str] = []

    async with ashared_resource_session(
        xdist_master_request,
        tmp_path_factory,
        "test_resource",
        setup_fn=lambda: calls.append("setup"),
        teardown_fn=lambda: calls.append("teardown"),
    ) as owns_setup:
        assert owns_setup is True

    assert calls == ["setup", "teardown"]


@pytest.mark.asyncio
async def test_ashared_session_setup_failure_cleans_up(xdist_master_request, tmp_path_factory):
    calls: list[str] = []

    async def _async_setup_boom() -> None:
        calls.append("setup")
        raise _SetupBoomError

    with pytest.raises(_SetupBoomError):
        async with ashared_resource_session(
            xdist_master_request,
            tmp_path_factory,
            "test_resource",
            setup_fn=_async_setup_boom,
            teardown_fn=lambda: calls.append("teardown"),
        ):
            calls.append("body")  # must never run

    assert calls == ["setup", "teardown"]


@pytest.mark.asyncio
async def test_ashared_session_waits_with_registry_under_xdist(monkeypatch: pytest.MonkeyPatch, tmp_path_factory):
    worker_request = SimpleNamespace(config=SimpleNamespace(workerinput={"workerid": "gw0"}))
    calls: list[str] = []

    class _FakeRegistry:
        def __init__(self, _root, _name) -> None:
            self.unregistered: list[str] = []

        @staticmethod
        def register(_token: str) -> bool:
            return False  # someone else owns the setup

        @staticmethod
        def wait_ready(*, timeout: timedelta) -> None:
            assert timeout > timedelta(0)

        def unregister(self, token: str) -> bool:
            self.unregistered.append(token)
            return False  # other users remain: no teardown here

    created: list[_FakeRegistry] = []

    def _fake_registry_cls(root, name) -> _FakeRegistry:
        reg = _FakeRegistry(root, name)
        created.append(reg)
        return reg

    monkeypatch.setattr("pytest_simcore.helpers.xdist.SharedResourceRegistry", _fake_registry_cls)

    async with ashared_resource_session(
        worker_request,
        tmp_path_factory,
        "test_resource",
        setup_fn=lambda: calls.append("setup"),
        teardown_fn=lambda: calls.append("teardown"),
        wait_timeout=timedelta(seconds=1),
    ) as owns_setup:
        assert owns_setup is False
        assert calls == []

    assert calls == []
    assert len(created[0].unregistered) == 1


def test_write_lock_releases_marker_when_reader_drain_times_out(tmp_path_factory):
    """a writer whose drain phase times out must NOT leave its marker behind: a stale marker
    would poison every subsequent reader/writer acquisition until removed by hand
    """
    lock = ReaderWriterLock(tmp_path_factory.mktemp("rw"), "daemon")
    stuck_reader = "stuck-reader"
    giving_up_writer = "giving-up-writer"
    next_writer = "next-writer"

    writer_never_started = lock.write_lock(token=giving_up_writer, timeout=timedelta(milliseconds=100))
    with lock.read_lock(token=stuck_reader), pytest.raises(TimeoutError), writer_never_started:
        pass  # the writer must never enter its section while the reader is stuck

    # the abandoned writer's marker must be gone: a later writer acquires cleanly
    with lock.write_lock(token=next_writer, timeout=timedelta(seconds=5)):
        pass
