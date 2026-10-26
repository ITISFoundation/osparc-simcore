# pylint: disable=protected-access

import json
from datetime import timedelta
from types import SimpleNamespace

import pytest
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from pytest_simcore.helpers import playwright as playwright_helpers
from pytest_simcore.helpers.playwright import (
    SOCKETIO_MESSAGE_PREFIX,
    NodeProgressType,
    SocketIONodeProgressCompleteWaiter,
    _ensure_service_iframe_attached,
)

_NODE_ID = "d00cb7e0-8b78-4d5c-9b57-2a1f6c6a1234"


def _socketio_message(name: str, obj: dict) -> str:
    return f"{SOCKETIO_MESSAGE_PREFIX}{json.dumps([name, obj])}"


def _service_status_message(node_id: str, service_state: str) -> str:
    return _socketio_message("serviceStatus", {"service_uuid": node_id, "service_state": service_state})


def _node_progress_message(node_id: str, progress_type: NodeProgressType, ratio: float) -> str:
    return _socketio_message(
        "nodeProgress",
        {
            "node_id": node_id,
            "progress_type": progress_type.value,
            "progress_report": {"actual_value": ratio, "total": 1.0},
        },
    )


def test_idle_state_within_grace_period_does_not_fail_fast():
    waiter = SocketIONodeProgressCompleteWaiter(node_id=_NODE_ID)

    done = waiter(_service_status_message(_NODE_ID, "idle"))

    assert done is False
    assert waiter.success is False


def test_idle_state_after_grace_period_fails_fast():
    waiter = SocketIONodeProgressCompleteWaiter(node_id=_NODE_ID, min_idle_before_fail_fast=timedelta(seconds=0))

    done = waiter(_service_status_message(_NODE_ID, "idle"))

    assert done is True
    assert waiter.success is False


def test_idle_state_grace_period_is_anchored_on_first_status_message():
    waiter = SocketIONodeProgressCompleteWaiter(node_id=_NODE_ID)

    # first idle message: well within the grace period
    first_done = waiter(_service_status_message(_NODE_ID, "idle"))
    assert first_done is False
    assert waiter.success is False

    # simulate that the node has been idle since well before the grace period,
    # without resetting the timer on this second message
    assert waiter._first_service_status_received_at is not None  # noqa: SLF001
    waiter._first_service_status_received_at -= timedelta(seconds=20)  # noqa: SLF001

    second_done = waiter(_service_status_message(_NODE_ID, "idle"))

    assert second_done is True
    assert waiter.success is False


def test_idle_within_grace_period_still_triggers_stale_progress_fallback():
    # NOTE: regression test — an idle SERVICE_STATUS message that stays within
    # its own idle grace period must not bypass the general stale-progress
    # fallback check (`max_idle_timeout`), otherwise the waiter could wait
    # forever if the backend keeps reporting "idle" but never emits any
    # nodeProgress message.
    waiter = SocketIONodeProgressCompleteWaiter(
        node_id=_NODE_ID,
        max_idle_timeout=timedelta(seconds=0),
        min_idle_before_fail_fast=timedelta(hours=1),
    )

    done = waiter(_service_status_message(_NODE_ID, "idle"))

    assert done is True
    assert waiter.success is True


def test_failed_state_fails_fast_immediately():
    waiter = SocketIONodeProgressCompleteWaiter(node_id=_NODE_ID)

    done = waiter(_service_status_message(_NODE_ID, "failed"))

    assert done is True
    assert waiter.success is False


def test_node_progress_reaching_completion_marks_success():
    waiter = SocketIONodeProgressCompleteWaiter(node_id=_NODE_ID)

    required_types = sorted(NodeProgressType.required_types_for_started_service(), key=lambda t: t.value)
    done = False
    for progress_type in required_types:
        done = waiter(_node_progress_message(_NODE_ID, progress_type, 1.0))

    assert done is True
    assert waiter.success is True


_SERVICE_FRAME_URL = f"https://{_NODE_ID}.services.example.org/lab"


class _FakeIframeLocator:
    def __init__(self, page: _FakePage) -> None:
        self._page = page

    @property
    def first(self) -> _FakeIframeLocator:
        return self

    def evaluate(self, _script) -> None:
        if self._page.evaluate_error is not None:
            raise self._page.evaluate_error
        self._page.navigations += 1
        self._page.frames.append(SimpleNamespace(url=_SERVICE_FRAME_URL))


class _FakePage:
    """Duck-typed subset of `playwright.sync_api.Page` used by `_ensure_service_iframe_attached`"""

    def __init__(
        self,
        *,
        frame_attached: bool,
        iframe_src_set: bool = True,
        evaluate_error: Exception | None = None,
    ) -> None:
        self.frames: list[SimpleNamespace] = (
            [SimpleNamespace(url=_SERVICE_FRAME_URL)]
            if frame_attached
            else [SimpleNamespace(url="https://osparc.example.org/")]
        )
        self.navigations = 0
        self._iframe_src_set = iframe_src_set
        self.evaluate_error = evaluate_error

    def locator(self, _selector) -> _FakeIframeLocator:
        return _FakeIframeLocator(self)

    def wait_for_function(self, _expression, **_kwargs) -> None:
        # NOTE: the real call passes the node id as `arg`: the iframe src must contain it
        # once the UI navigated it
        if not self._iframe_src_set:
            raise PlaywrightTimeoutError()  # raised by Playwright when the timeout elapses

    def wait_for_timeout(self, _milliseconds) -> None:
        pass


@pytest.fixture()
def _no_frame_attach_grace(monkeypatch: pytest.MonkeyPatch):
    # NOTE: keep the unattached-frame tests from waiting out the real grace window
    monkeypatch.setattr(playwright_helpers, "_SERVICE_FRAME_ATTACH_TIMEOUT", 0)


def test_healthy_service_iframe_is_left_untouched():
    page = _FakePage(frame_attached=True)

    _ensure_service_iframe_attached(page, _NODE_ID)  # type: ignore[arg-type]

    assert page.navigations == 0


def test_unattached_service_iframe_is_re_navigated(_no_frame_attach_grace):
    # NOTE: regression test for microsoft/playwright#43007: the service UI is rendered
    # but its content frame is missing from page.frames, so queries hang forever
    page = _FakePage(frame_attached=False)

    _ensure_service_iframe_attached(page, _NODE_ID)  # type: ignore[arg-type]

    assert page.navigations == 1


def test_service_iframe_not_navigated_yet_is_left_untouched():
    # NOTE: regression test: the UI sets the iframe src asynchronously (IframeHandler.js),
    # so an iframe that never navigated must not be treated as the attach bug nor reloaded
    page = _FakePage(frame_attached=False, iframe_src_set=False)

    _ensure_service_iframe_attached(page, _NODE_ID)  # type: ignore[arg-type]

    assert page.navigations == 0


def test_failing_iframe_recovery_is_not_raising(_no_frame_attach_grace):
    # NOTE: the recovery is best-effort: a Playwright error while re-navigating must not
    # abort the service-ready helpers, which must fail with their own original error
    page = _FakePage(frame_attached=False, evaluate_error=PlaywrightError("boom"))

    _ensure_service_iframe_attached(page, _NODE_ID)  # type: ignore[arg-type]
