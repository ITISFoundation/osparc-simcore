"""Waits for a pipeline that runs on the backend from the browser."""

import logging
import re
from dataclasses import dataclass
from datetime import timedelta
from typing import Final

import pytest
from models_library.projects_state import RunningState
from playwright.sync_api import (
    Page,
    Request,
)
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from .logging_tools import ContextMessages, log_context
from .playwright_constants import MINUTE, SECOND
from .playwright_diagnostics import _pipeline_wait_raised_message
from .playwright_websocket import (
    RobustWebSocket,
    SocketIOProjectStateUpdatedWaiter,
    decode_socketio_42_message,
    retrieve_project_state_from_decoded_message,
)

_FAIL_FAST_COMPUTATIONAL_STATES: Final[tuple[RunningState, ...]] = (
    RunningState.FAILED,
    RunningState.ABORTED,
)


def wait_for_pipeline_state(
    current_state: RunningState,
    *,
    websocket: RobustWebSocket,
    project_uuid: str,
    if_in_states: tuple[RunningState, ...],
    expected_states: tuple[RunningState, ...],
    timeout_ms: int,
) -> RunningState:
    if current_state in if_in_states:
        waiter = SocketIOProjectStateUpdatedWaiter(
            expected_states=expected_states + _FAIL_FAST_COMPUTATIONAL_STATES,
            project_uuid=project_uuid,
        )
        # NOTE: the hints describe a wait that ran out of time. Any other error here (a socket that
        # never connected or could not be reattached) says nothing about the backend
        wait_timed_out = False
        with log_context(
            logging.INFO,
            msg=ContextMessages(
                starting=f"wait for one of {expected_states=} (timeout {timedelta(milliseconds=timeout_ms)})",
                done=lambda: f"wait for one of {expected_states=}, pipeline reached {current_state=}",
                raised=lambda: _pipeline_wait_raised_message(
                    waiter.last_state_seen() or current_state,
                    expected_states,
                    timed_out=wait_timed_out,
                ),
            ),
        ):
            try:
                with websocket.expect_event("framereceived", waiter, timeout=timeout_ms) as event:
                    current_state = retrieve_project_state_from_decoded_message(decode_socketio_42_message(event.value))
            except PlaywrightTimeoutError:
                wait_timed_out = True
                raise

            if current_state in _FAIL_FAST_COMPUTATIONAL_STATES and current_state not in expected_states:
                pytest.fail(f"❌ Pipeline failed fast with state {current_state}. Expected one of {expected_states} ❌")
    return current_state


_RUNNING_STATES: Final[tuple[RunningState, ...]] = (
    RunningState.PUBLISHED,
    RunningState.PENDING,
    RunningState.WAITING_FOR_CLUSTER,
    RunningState.WAITING_FOR_RESOURCES,
    RunningState.STARTED,
)

_RUN_PIPELINE_MAX_WAIT_TIME: Final[int] = 60 * SECOND

_COMPUTATION_START_REQUEST_PATTERN: Final[re.Pattern[str]] = re.compile(r"/computations")

_COMPUTATION_START_REQUEST_TIMEOUT: Final[int] = 35 * SECOND


def _computation_started_predicate(request: Request) -> bool:
    return bool(re.search(_COMPUTATION_START_REQUEST_PATTERN, request.url) and request.method.upper() == "POST")


@dataclass(frozen=True, slots=True, kw_only=True)
class PipelineStageTimeouts:
    """Per-transition timeout budgets for a staged pipeline wait.

    Needed for autoscaled deployments, where a cold cluster/worker scale-up can take several
    minutes without the pipeline actually being stuck. Mirrors the legacy sleepers state machine:
    PUBLISHED/PENDING -> [WAITING_FOR_CLUSTER] -> [WAITING_FOR_RESOURCES] -> STARTED -> SUCCESS
    """

    published_or_pending_ms: int = 1 * MINUTE
    waiting_for_cluster_ms: int = 5 * MINUTE
    waiting_for_resources_ms: int = 5 * MINUTE
    started_ms: int = 5 * MINUTE

    @property
    def total_ms(self) -> int:
        """Upper bound covering every stage sequentially, for wrappers spanning the whole wait."""
        return (
            self.published_or_pending_ms + self.waiting_for_cluster_ms + self.waiting_for_resources_ms + self.started_ms
        )


def wait_for_computation_done(
    current_state: RunningState,
    *,
    websocket: RobustWebSocket,
    project_uuid: str,
    stage_timeouts: PipelineStageTimeouts | int,
) -> RunningState:
    """Waits for an already-started computational pipeline to reach a final state.

    Pass an ``int`` for a single flat timeout budget covering the whole run (simple/
    non-autoscaled deployments), or a `PipelineStageTimeouts` to instead wait through each
    transition with its own budget (autoscaled deployments).
    """
    if isinstance(stage_timeouts, int):
        return wait_for_pipeline_state(
            current_state,
            websocket=websocket,
            project_uuid=project_uuid,
            if_in_states=_RUNNING_STATES,
            expected_states=(RunningState.SUCCESS,),
            timeout_ms=stage_timeouts,
        )

    current_state = wait_for_pipeline_state(
        current_state,
        websocket=websocket,
        project_uuid=project_uuid,
        if_in_states=(RunningState.PUBLISHED, RunningState.PENDING),
        expected_states=(
            RunningState.WAITING_FOR_CLUSTER,
            RunningState.WAITING_FOR_RESOURCES,
            RunningState.STARTED,
            RunningState.SUCCESS,
        ),
        timeout_ms=stage_timeouts.published_or_pending_ms,
    )
    current_state = wait_for_pipeline_state(
        current_state,
        websocket=websocket,
        project_uuid=project_uuid,
        if_in_states=(RunningState.WAITING_FOR_CLUSTER,),
        expected_states=(
            RunningState.WAITING_FOR_RESOURCES,
            RunningState.STARTED,
            RunningState.SUCCESS,
        ),
        timeout_ms=stage_timeouts.waiting_for_cluster_ms,
    )
    current_state = wait_for_pipeline_state(
        current_state,
        websocket=websocket,
        project_uuid=project_uuid,
        if_in_states=(RunningState.WAITING_FOR_RESOURCES,),
        expected_states=(
            RunningState.STARTED,
            RunningState.SUCCESS,
        ),
        timeout_ms=stage_timeouts.waiting_for_resources_ms,
    )
    return wait_for_pipeline_state(
        current_state,
        websocket=websocket,
        project_uuid=project_uuid,
        if_in_states=(RunningState.STARTED,),
        expected_states=(RunningState.SUCCESS,),
        timeout_ms=stage_timeouts.started_ms,
    )


def run_pipeline_and_wait_done(
    page: Page,
    websocket: RobustWebSocket,
    *,
    project_uuid: str,
    run_button_test_id: str = "runStudyBtn",
    timeout_ms: int = _RUN_PIPELINE_MAX_WAIT_TIME,
    stage_timeouts: PipelineStageTimeouts | None = None,
) -> RunningState:
    """Clicks the "Run" button and waits until the pipeline reaches a final state.

    By default (``stage_timeouts=None``) this waits within a single ``timeout_ms`` budget. Pass
    ``stage_timeouts`` to instead wait through each transition with its own budget, needed for
    autoscaled deployments (see `PipelineStageTimeouts`).

    Port of the legacy `TutorialBase.runPipeline()` + `TutorialBase.waitForStudyDone()`.
    """
    # NOTE: mirrors `start_and_stop_pipeline` (tests/conftest.py): expected_states is restricted to
    # the "actively running" states only (no NOT_STARTED/UNKNOWN/SUCCESS/FAILED/ABORTED) so a stray
    # `projectStateUpdated` frame still reporting the pre-run state can't race with the actual run
    # trigger and be mistaken for a final state; the `POST /computations` request is also checked
    # to confirm the click really triggered a computation.
    waiter = SocketIOProjectStateUpdatedWaiter(expected_states=_RUNNING_STATES, project_uuid=project_uuid)
    with log_context(
        logging.INFO,
        f"Running pipeline and waiting for it to complete (timeout {timedelta(milliseconds=timeout_ms)})",
    ) as ctx:
        with (
            websocket.expect_event("framereceived", waiter, timeout=timeout_ms) as event,
            page.expect_request(
                _computation_started_predicate, timeout=_COMPUTATION_START_REQUEST_TIMEOUT
            ) as request_info,
        ):
            page.get_by_test_id(run_button_test_id).click()
        response = request_info.value.response()
        assert response
        ctx.logger.info("POST /computations request response: %s", f"{response.status=}")
        assert response.ok, f"{response.json()}"
        current_state = retrieve_project_state_from_decoded_message(decode_socketio_42_message(event.value))
        current_state = wait_for_computation_done(
            current_state,
            websocket=websocket,
            project_uuid=project_uuid,
            stage_timeouts=stage_timeouts if stage_timeouts is not None else timeout_ms,
        )
        assert current_state == RunningState.SUCCESS, f"❌ Pipeline finished with {current_state} ❌"
        return current_state
