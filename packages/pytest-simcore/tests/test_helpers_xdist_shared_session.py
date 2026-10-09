# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

from datetime import timedelta
from types import SimpleNamespace

import pytest
from pytest_simcore.helpers.xdist import daemon_churn_access, shared_resource_session


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
