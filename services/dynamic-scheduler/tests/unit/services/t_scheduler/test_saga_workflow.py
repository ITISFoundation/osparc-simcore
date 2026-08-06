# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument

from collections.abc import Callable, Coroutine
from typing import Any

import pytest
from fastapi import FastAPI
from pytest_mock import MockerFixture
from simcore_service_dynamic_scheduler.services.t_scheduler import (
    WorkflowEngine,
    get_workflow_engine,
)
from simcore_service_dynamic_scheduler.services.t_scheduler._base_workflow import SagaWorkflow
from simcore_service_dynamic_scheduler.services.t_scheduler._dependencies import (
    get_temporalio_client,
)
from simcore_service_dynamic_scheduler.services.t_scheduler._errors import ActivityNotInFailedError
from simcore_service_dynamic_scheduler.services.t_scheduler._models import (
    ActivityCompleted,
    ActivityFailed,
    ActivityStarted,
    CompensationCompleted,
    CompensationFailed,
    CompensationStarted,
    Decision,
    DecisionReceived,
    ResolutionSignal,
    StateChanged,
    WorkflowEventBase,
    WorkflowState,
)
from temporalio.client import Client
from temporalio.exceptions import WorkflowAlreadyStartedError
from tenacity import AsyncRetrying, stop_after_delay, wait_fixed

_POLL_WAIT = wait_fixed(0.1)
_POLL_STOP = stop_after_delay(5)


class _Optional:
    """Entry that may or may not appear (e.g., parallel activity racing with a failure)."""

    __slots__ = ("entry",)

    def __init__(self, entry: str) -> None:
        self.entry = entry


class _Unordered:
    """All required entries must appear in any order. _Optional entries may or may not appear."""

    __slots__ = ("entries",)

    def __init__(self, *entries: str | _Optional) -> None:
        self.entries = entries


type _ExpectedEntry = str | _Unordered


def assert_call_log_order(
    call_log: list[str],
    expected: list[_ExpectedEntry],
    *,
    skipped_activities: set[str] | None = None,
) -> None:
    optional_allowed: set[str] = set()
    for entry in expected:
        if isinstance(entry, _Unordered):
            for e in entry.entries:
                if isinstance(e, _Optional):
                    optional_allowed.add(e.entry)

    required_log = [e for e in call_log if e not in optional_allowed]
    actual_optional = [e for e in call_log if e in optional_allowed]

    assert set(actual_optional) <= optional_allowed, (
        f"Unexpected optional entries: {set(actual_optional) - optional_allowed}"
    )

    pos = 0
    for entry in expected:
        if isinstance(entry, str):
            assert pos < len(required_log), f"Expected {entry!r} but log ended at position {pos}. Log: {required_log}"
            assert required_log[pos] == entry, (
                f"Expected {entry!r} at position {pos} but got {required_log[pos]!r}. Log: {required_log}"
            )
            pos += 1
        elif isinstance(entry, _Unordered):
            required = [e for e in entry.entries if isinstance(e, str)]
            n = len(required)
            chunk = required_log[pos : pos + n]
            assert len(chunk) == n and set(chunk) == set(required), (  # noqa: PT018
                f"Expected {set(required)} in any order at position {pos} but got {chunk}. Log: {required_log}"
            )
            pos += n

    assert pos == len(required_log), f"Unexpected trailing entries: {required_log[pos:]}. Full log: {call_log}"

    # Compensation invariant: if any compensation ran, every executed step must be compensated
    executed = {e.removeprefix("execute:") for e in call_log if e.startswith("execute:")}
    compensated = {e.removeprefix("compensate:") for e in call_log if e.startswith("compensate:")}
    if compensated:
        missing = executed - compensated - (skipped_activities or set())
        assert not missing, (
            f"Steps executed but not compensated: {missing}. Executed: {executed}, Compensated: {compensated}"
        )


class _UnorderedHistory:
    __slots__ = ("entries",)

    def __init__(self, *entries: WorkflowEventBase) -> None:
        self.entries = entries


type _ExpectedHistoryEntry = WorkflowEventBase | _UnorderedHistory


def _matches_event(actual: WorkflowEventBase, expected: WorkflowEventBase) -> bool:
    """Check if actual event matches expected, comparing only explicitly-set fields + kind."""
    compare_fields = expected.model_fields_set | {"kind"}
    actual_data = actual.model_dump(exclude={"timestamp"})
    expected_data = expected.model_dump(exclude={"timestamp"})
    return all(actual_data.get(k) == expected_data.get(k) for k in compare_fields)


async def assert_history_order(
    workflow_engine: WorkflowEngine,
    workflow_id: str,
    expected: list[_ExpectedHistoryEntry],
) -> None:
    history = await workflow_engine.history(workflow_id)
    actual = history.events

    pos = 0
    for entry in expected:
        if isinstance(entry, WorkflowEventBase):
            assert pos < len(actual), f"Expected {entry!r} but history ended at position {pos}. History: {actual}"
            assert _matches_event(actual[pos], entry), (
                f"Expected {entry!r} at position {pos} but got {actual[pos]!r}. History: {actual}"
            )
            pos += 1
        elif isinstance(entry, _UnorderedHistory):
            n = len(entry.entries)
            chunk = actual[pos : pos + n]
            assert len(chunk) == n, (
                f"Expected {n} unordered entries at position {pos} but got {len(chunk)}. History: {actual}"
            )
            matched: set[int] = set()
            for exp in entry.entries:
                found = False
                for i, act in enumerate(chunk):
                    if i not in matched and _matches_event(act, exp):
                        matched.add(i)
                        found = True
                        break
                assert found, f"No match for {exp!r} in chunk {list(chunk)!r} at position {pos}. History: {actual}"
            pos += n

    assert pos == len(actual), f"Unexpected trailing entries: {actual[pos:]}. Full history: {actual}"


@pytest.fixture
def workflow_engine(app: FastAPI) -> WorkflowEngine:
    return get_workflow_engine(app)


async def assert_workflow_status(
    workflow_engine: WorkflowEngine,
    workflow_id: str,
    *,
    state: WorkflowState,
    completed: set[str] | None = None,
    failed: dict[str, str] | None = None,
    compensated: set[str] | None = None,
    failed_compensations: dict[str, str] | None = None,
    skipped: set[str] | None = None,
    steps_total: int | None = None,
    progress: float | None = None,
    compensations_total: int | None = None,
    compensation_progress: float | None = None,
) -> None:
    status = await workflow_engine.status(workflow_id)
    assert status.state == state
    assert status.running_activities == set()
    if completed is not None:
        assert status.completed_activities == completed
    if failed is not None:
        assert set(status.failed_activities.keys()) == set(failed.keys())
    if compensated is not None:
        assert status.compensated_activities == compensated
    if failed_compensations is not None:
        assert set(status.failed_compensations.keys()) == set(failed_compensations.keys())
    if skipped is not None:
        assert status.skipped_activities == skipped
    if steps_total is not None:
        assert status.steps_total == steps_total
    if progress is not None:
        assert status.progress_percent == pytest.approx(progress)
    if compensations_total is not None:
        assert status.compensations_total == compensations_total
    if compensation_progress is not None:
        assert status.compensation_progress == pytest.approx(compensation_progress)


@pytest.fixture
def await_workflow_completed(
    workflow_engine: WorkflowEngine, app: FastAPI
) -> Callable[[str], Coroutine[Any, Any, dict[str, Any]]]:
    client: Client = get_temporalio_client(app)

    async def _await(workflow_id: str) -> dict[str, Any]:
        async for attempt in AsyncRetrying(wait=_POLL_WAIT, stop=_POLL_STOP, reraise=True):
            with attempt:
                status = await workflow_engine.status(workflow_id)
                assert status.state == WorkflowState.COMPLETED
        return await client.get_workflow_handle(workflow_id).result()

    return _await


@pytest.fixture
def await_workflow_failed(
    workflow_engine: WorkflowEngine,
) -> Callable[[str], Coroutine[Any, Any, None]]:
    async def _await(workflow_id: str) -> None:
        async for attempt in AsyncRetrying(wait=_POLL_WAIT, stop=_POLL_STOP, reraise=True):
            with attempt:
                status = await workflow_engine.status(workflow_id)
                assert status.state == WorkflowState.FAILED

    return _await


async def _assert_state_waiting_intervention(workflow_engine: WorkflowEngine, workflow_id: str) -> None:
    async for attempt in AsyncRetrying(wait=_POLL_WAIT, stop=_POLL_STOP, reraise=True):
        with attempt:
            status = await workflow_engine.status(workflow_id)
            assert status.state == WorkflowState.WAITING_INTERVENTION


async def test_happy_path(
    workflow_engine: WorkflowEngine,
    happy_path_workflow: type[SagaWorkflow],
    call_log: list[str],
    log_key: str,
    await_workflow_completed: Callable[[str], Coroutine[Any, Any, dict[str, Any]]],
):
    wf_id = "test-happy"
    await workflow_engine.start(
        happy_path_workflow.__name__,
        workflow_id=wf_id,
        context={"log_key": log_key},
    )
    result = await await_workflow_completed(wf_id)
    assert result["a_result"] == "done_a"
    assert result["b_result"] == "done_b"
    assert result["c_result"] == "done_c"

    assert_call_log_order(call_log, ["execute:a", "execute:b", "execute:c"])
    await assert_workflow_status(
        workflow_engine,
        wf_id,
        state=WorkflowState.COMPLETED,
        completed={"step_a", "step_b", "step_c"},
        failed={},
        compensated=set(),
        steps_total=3,
        progress=1.0,
    )
    await assert_history_order(
        workflow_engine,
        wf_id,
        [
            ActivityStarted(activity_name="step_a"),
            ActivityCompleted(activity_name="step_a"),
            ActivityStarted(activity_name="step_b"),
            ActivityCompleted(activity_name="step_b"),
            ActivityStarted(activity_name="step_c"),
            ActivityCompleted(activity_name="step_c"),
            StateChanged(new_state=WorkflowState.COMPLETED),
        ],
    )


async def test_auto_rollback_compensates_in_reverse(
    workflow_engine: WorkflowEngine,
    auto_rollback_workflow: type[SagaWorkflow],
    call_log: list[str],
    log_key: str,
    await_workflow_failed: Callable[[str], Coroutine[Any, Any, None]],
):
    wf_id = "test-auto-rollback"
    await workflow_engine.start(
        auto_rollback_workflow.__name__,
        workflow_id=wf_id,
        context={"log_key": log_key},
    )

    await await_workflow_failed(wf_id)

    assert_call_log_order(
        call_log,
        [
            "execute:a",
            "execute:b",
            "execute:failing",
            "compensate:failing",
            "compensate:b",
            "compensate:a",
        ],
    )
    await assert_workflow_status(
        workflow_engine,
        wf_id,
        state=WorkflowState.FAILED,
        completed={"step_a", "step_b"},
        failed={"step_failing": ""},
        compensated={"undo_failing", "undo_b", "undo_a"},
        steps_total=3,
    )
    await assert_history_order(
        workflow_engine,
        wf_id,
        [
            ActivityStarted(activity_name="step_a"),
            ActivityCompleted(activity_name="step_a"),
            ActivityStarted(activity_name="step_b"),
            ActivityCompleted(activity_name="step_b"),
            ActivityStarted(activity_name="step_failing"),
            ActivityFailed(activity_name="step_failing"),
            StateChanged(new_state=WorkflowState.COMPENSATING),
            CompensationStarted(activity_name="undo_failing"),
            CompensationCompleted(activity_name="undo_failing"),
            CompensationStarted(activity_name="undo_b"),
            CompensationCompleted(activity_name="undo_b"),
            CompensationStarted(activity_name="undo_a"),
            CompensationCompleted(activity_name="undo_a"),
            StateChanged(new_state=WorkflowState.FAILED),
        ],
    )


async def test_manual_intervention_skip(
    workflow_engine: WorkflowEngine,
    manual_intervention_workflow: type[SagaWorkflow],
    call_log: list[str],
    log_key: str,
    await_workflow_completed: Callable[[str], Coroutine[Any, Any, dict[str, Any]]],
):
    wf_id = "test-manual-skip"
    await workflow_engine.start(
        manual_intervention_workflow.__name__,
        workflow_id=wf_id,
        context={"log_key": log_key},
    )

    await _assert_state_waiting_intervention(workflow_engine, wf_id)

    await workflow_engine.signal(wf_id, activity_name="step_failing", decision=Decision.SKIP)

    result = await await_workflow_completed(wf_id)
    assert result.get("a_result") == "done_a"
    assert result.get("c_result") == "done_c"

    assert_call_log_order(call_log, ["execute:a", "execute:failing", "execute:c"])
    await assert_workflow_status(
        workflow_engine,
        wf_id,
        state=WorkflowState.COMPLETED,
        completed={"step_a", "step_c"},
        failed={},
        compensated=set(),
        skipped={"step_failing"},
        steps_total=3,
    )


async def test_manual_intervention_rollback(
    workflow_engine: WorkflowEngine,
    manual_intervention_workflow: type[SagaWorkflow],
    call_log: list[str],
    log_key: str,
    await_workflow_failed: Callable[[str], Coroutine[Any, Any, None]],
):
    wf_id = "test-manual-rollback"
    await workflow_engine.start(
        manual_intervention_workflow.__name__,
        workflow_id=wf_id,
        context={"log_key": log_key},
    )

    await _assert_state_waiting_intervention(workflow_engine, wf_id)

    await workflow_engine.signal(wf_id, activity_name="step_failing", decision=Decision.ROLLBACK)

    await await_workflow_failed(wf_id)

    assert_call_log_order(
        call_log,
        [
            "execute:a",
            "execute:failing",
            "compensate:failing",
            "compensate:a",
        ],
    )
    await assert_workflow_status(
        workflow_engine,
        wf_id,
        state=WorkflowState.FAILED,
        completed={"step_a"},
        failed={"step_failing": ""},
        compensated={"undo_failing", "undo_a"},
        steps_total=3,
    )


@pytest.mark.parametrize("retry_count", [3])
async def test_manual_intervention_retry(
    workflow_engine: WorkflowEngine,
    manual_intervention_workflow: type[SagaWorkflow],
    call_log: list[str],
    log_key: str,
    retry_count: int,
    await_workflow_completed: Callable[[str], Coroutine[Any, Any, dict[str, Any]]],
):
    wf_id = "test-manual-retry"
    await workflow_engine.start(
        manual_intervention_workflow.__name__,
        workflow_id=wf_id,
        context={"log_key": log_key},
    )

    await _assert_state_waiting_intervention(workflow_engine, wf_id)

    for _ in range(retry_count):
        # Retry will fail again since the activity always fails,
        # which means we'll be back at waiting_intervention.
        await workflow_engine.signal(wf_id, activity_name="step_failing", decision=Decision.RETRY)
        await _assert_state_waiting_intervention(workflow_engine, wf_id)

    # Now skip to let the workflow complete
    await workflow_engine.signal(wf_id, activity_name="step_failing", decision=Decision.SKIP)

    result = await await_workflow_completed(wf_id)
    assert result.get("a_result") == "done_a"
    assert result.get("c_result") == "done_c"

    assert_call_log_order(
        call_log,
        [
            "execute:a",
            *["execute:failing"] * (retry_count + 1),
            "execute:c",
        ],
    )
    await assert_workflow_status(
        workflow_engine,
        wf_id,
        state=WorkflowState.COMPLETED,
        completed={"step_a", "step_c"},
        failed={},
        compensated=set(),
        skipped={"step_failing"},
        steps_total=3,
    )
    await assert_history_order(
        workflow_engine,
        wf_id,
        [
            ActivityStarted(activity_name="step_a"),
            ActivityCompleted(activity_name="step_a"),
            *[
                entry
                for _ in range(retry_count)
                for entry in [
                    ActivityStarted(activity_name="step_failing"),
                    ActivityFailed(activity_name="step_failing"),
                    StateChanged(new_state=WorkflowState.WAITING_INTERVENTION),
                    DecisionReceived(activity_name="step_failing", decision=Decision.RETRY),
                ]
            ],
            ActivityStarted(activity_name="step_failing"),
            ActivityFailed(activity_name="step_failing"),
            StateChanged(new_state=WorkflowState.WAITING_INTERVENTION),
            DecisionReceived(activity_name="step_failing", decision=Decision.SKIP),
            ActivityStarted(activity_name="step_c"),
            ActivityCompleted(activity_name="step_c"),
            StateChanged(new_state=WorkflowState.COMPLETED),
        ],
    )


async def test_parallel_execution(
    workflow_engine: WorkflowEngine,
    parallel_workflow: type[SagaWorkflow],
    call_log: list[str],
    log_key: str,
    await_workflow_completed: Callable[[str], Coroutine[Any, Any, dict[str, Any]]],
):
    wf_id = "test-parallel"
    await workflow_engine.start(
        parallel_workflow.__name__,
        workflow_id=wf_id,
        context={"log_key": log_key},
    )
    result = await await_workflow_completed(wf_id)
    assert result["a_result"] == "done_a"
    assert result["b_result"] == "done_b"
    assert result["c_result"] == "done_c"

    assert_call_log_order(
        call_log,
        [
            "execute:a",
            _Unordered("execute:b", "execute:c"),
        ],
    )
    await assert_workflow_status(
        workflow_engine,
        wf_id,
        state=WorkflowState.COMPLETED,
        completed={"step_a", "step_b", "step_c"},
        failed={},
        compensated=set(),
        steps_total=3,
        progress=1.0,
    )
    await assert_history_order(
        workflow_engine,
        wf_id,
        [
            ActivityStarted(activity_name="step_a"),
            ActivityCompleted(activity_name="step_a"),
            _UnorderedHistory(
                ActivityStarted(activity_name="step_b"),
                ActivityStarted(activity_name="step_c"),
                ActivityCompleted(activity_name="step_b"),
                ActivityCompleted(activity_name="step_c"),
            ),
            StateChanged(new_state=WorkflowState.COMPLETED),
        ],
    )


async def test_workflow_cancellation(
    workflow_engine: WorkflowEngine,
    manual_intervention_workflow: type[SagaWorkflow],
    call_log: list[str],
    log_key: str,
    await_workflow_failed: Callable[[str], Coroutine[Any, Any, None]],
):
    wf_id = "test-cancel"
    await workflow_engine.start(
        manual_intervention_workflow.__name__,
        workflow_id=wf_id,
        context={"log_key": log_key},
    )

    await _assert_state_waiting_intervention(workflow_engine, wf_id)

    await workflow_engine.cancel(wf_id)

    await await_workflow_failed(wf_id)

    assert_call_log_order(call_log, ["execute:a", "execute:failing", "compensate:failing", "compensate:a"])
    await assert_workflow_status(
        workflow_engine,
        wf_id,
        state=WorkflowState.FAILED,
        completed={"step_a"},
        failed={"step_failing": ""},
        compensated={"undo_failing", "undo_a"},
        steps_total=3,
    )
    await assert_history_order(
        workflow_engine,
        wf_id,
        [
            ActivityStarted(activity_name="step_a"),
            ActivityCompleted(activity_name="step_a"),
            ActivityStarted(activity_name="step_failing"),
            ActivityFailed(activity_name="step_failing"),
            StateChanged(new_state=WorkflowState.WAITING_INTERVENTION),
            StateChanged(new_state=WorkflowState.COMPENSATING),
            CompensationStarted(activity_name="undo_failing"),
            CompensationCompleted(activity_name="undo_failing"),
            CompensationStarted(activity_name="undo_a"),
            CompensationCompleted(activity_name="undo_a"),
            StateChanged(new_state=WorkflowState.FAILED),
        ],
    )


async def test_mutual_exclusion(
    workflow_engine: WorkflowEngine,
    manual_intervention_workflow: type[SagaWorkflow],
    happy_path_workflow: type[SagaWorkflow],
    call_log: list[str],
    log_key: str,
    await_workflow_failed: Callable[[str], Coroutine[Any, Any, None]],
):
    wf_id = "test-mutual-exclusion"
    await workflow_engine.start(
        manual_intervention_workflow.__name__,
        workflow_id=wf_id,
        context={"log_key": log_key},
    )

    await _assert_state_waiting_intervention(workflow_engine, wf_id)

    with pytest.raises(WorkflowAlreadyStartedError):
        await workflow_engine.start(
            happy_path_workflow.__name__,
            workflow_id="test-mutual-exclusion",
            context={"log_key": log_key},
        )

    await workflow_engine.signal(wf_id, activity_name="step_failing", decision=Decision.ROLLBACK)
    await await_workflow_failed(wf_id)

    assert_call_log_order(
        call_log,
        ["execute:a", "execute:failing", "compensate:failing", "compensate:a"],
    )
    await assert_workflow_status(
        workflow_engine,
        wf_id,
        state=WorkflowState.FAILED,
        completed={"step_a"},
        failed={"step_failing": ""},
        compensated={"undo_failing", "undo_a"},
        steps_total=3,
    )


async def test_signal_invalid_activity_raises(
    workflow_engine: WorkflowEngine,
    manual_intervention_workflow: type[SagaWorkflow],
    call_log: list[str],
    log_key: str,
    await_workflow_failed: Callable[[str], Coroutine[Any, Any, None]],
):
    wf_id = "test-signal-invalid"
    await workflow_engine.start(
        manual_intervention_workflow.__name__,
        workflow_id=wf_id,
        context={"log_key": log_key},
    )

    await _assert_state_waiting_intervention(workflow_engine, wf_id)

    with pytest.raises(ActivityNotInFailedError, match="not_a_real_activity"):
        await workflow_engine.signal(wf_id, activity_name="not_a_real_activity", decision=Decision.SKIP)

    # The valid activity is still waiting — resolve it so the test cleans up
    await workflow_engine.signal(wf_id, activity_name="step_failing", decision=Decision.ROLLBACK)
    await await_workflow_failed(wf_id)


async def test_query_status(
    workflow_engine: WorkflowEngine,
    manual_intervention_workflow: type[SagaWorkflow],
    call_log: list[str],
    log_key: str,
    await_workflow_failed: Callable[[str], Coroutine[Any, Any, None]],
):
    wf_id = "test-query"
    await workflow_engine.start(
        manual_intervention_workflow.__name__,
        workflow_id=wf_id,
        context={"log_key": log_key},
    )

    await _assert_state_waiting_intervention(workflow_engine, wf_id)

    status = await workflow_engine.status(wf_id)
    assert status.state == WorkflowState.WAITING_INTERVENTION
    assert "step_failing" in status.failed_activities
    assert status.running_activities == set()

    await workflow_engine.signal(wf_id, activity_name="step_failing", decision=Decision.ROLLBACK)
    await await_workflow_failed(wf_id)

    assert_call_log_order(
        call_log,
        ["execute:a", "execute:failing", "compensate:failing", "compensate:a"],
    )
    await assert_workflow_status(
        workflow_engine,
        wf_id,
        state=WorkflowState.FAILED,
        completed={"step_a"},
        failed={"step_failing": ""},
        compensated={"undo_failing", "undo_a"},
        steps_total=3,
    )


async def test_status_on_completed_workflow(
    workflow_engine: WorkflowEngine,
    happy_path_workflow: type[SagaWorkflow],
    call_log: list[str],
    log_key: str,
    await_workflow_completed: Callable[[str], Coroutine[Any, Any, dict[str, Any]]],
):
    wf_id = "test-status-completed"
    await workflow_engine.start(
        happy_path_workflow.__name__,
        workflow_id=wf_id,
        context={"log_key": log_key},
    )

    await await_workflow_completed(wf_id)

    # status() must work even after the workflow has completed
    status = await workflow_engine.status(wf_id)
    assert status.state == WorkflowState.COMPLETED
    assert status.failed_activities == {}
    assert status.completed_activities == {"step_a", "step_b", "step_c"}

    assert_call_log_order(call_log, ["execute:a", "execute:b", "execute:c"])
    await assert_workflow_status(
        workflow_engine,
        wf_id,
        state=WorkflowState.COMPLETED,
        completed={"step_a", "step_b", "step_c"},
        failed={},
        compensated=set(),
        steps_total=3,
        progress=1.0,
    )


async def test_parallel_auto_rollback(
    workflow_engine: WorkflowEngine,
    parallel_auto_rollback_workflow: type[SagaWorkflow],
    call_log: list[str],
    log_key: str,
    await_workflow_failed: Callable[[str], Coroutine[Any, Any, None]],
):
    wf_id = "test-parallel-auto-rollback"
    await workflow_engine.start(
        parallel_auto_rollback_workflow.__name__,
        workflow_id=wf_id,
        context={"log_key": log_key},
    )

    await await_workflow_failed(wf_id)

    assert_call_log_order(
        call_log,
        [
            "execute:a",
            _Unordered(_Optional("execute:b"), "execute:failing"),
            _Unordered(_Optional("compensate:b"), "compensate:failing"),
            "compensate:a",
        ],
    )
    await assert_workflow_status(workflow_engine, wf_id, state=WorkflowState.FAILED, steps_total=3)


async def test_parallel_manual_intervention_skip(
    workflow_engine: WorkflowEngine,
    parallel_manual_intervention_workflow: type[SagaWorkflow],
    call_log: list[str],
    log_key: str,
    await_workflow_completed: Callable[[str], Coroutine[Any, Any, dict[str, Any]]],
):
    wf_id = "test-parallel-manual-skip"
    await workflow_engine.start(
        parallel_manual_intervention_workflow.__name__,
        workflow_id=wf_id,
        context={"log_key": log_key},
    )

    await _assert_state_waiting_intervention(workflow_engine, wf_id)

    await workflow_engine.signal(wf_id, activity_name="step_failing", decision=Decision.SKIP)

    result = await await_workflow_completed(wf_id)
    assert result.get("a_result") == "done_a"
    assert result.get("b_result") == "done_b"

    assert_call_log_order(
        call_log,
        [
            "execute:a",
            _Unordered("execute:b", "execute:failing"),
        ],
    )
    await assert_workflow_status(
        workflow_engine,
        wf_id,
        state=WorkflowState.COMPLETED,
        completed={"step_a", "step_b"},
        failed={},
        compensated=set(),
        skipped={"step_failing"},
        steps_total=3,
    )


async def test_parallel_manual_intervention_rollback(
    workflow_engine: WorkflowEngine,
    parallel_manual_intervention_workflow: type[SagaWorkflow],
    call_log: list[str],
    log_key: str,
    await_workflow_failed: Callable[[str], Coroutine[Any, Any, None]],
):
    wf_id = "test-parallel-manual-rollback"
    await workflow_engine.start(
        parallel_manual_intervention_workflow.__name__,
        workflow_id=wf_id,
        context={"log_key": log_key},
    )

    await _assert_state_waiting_intervention(workflow_engine, wf_id)

    await workflow_engine.signal(wf_id, activity_name="step_failing", decision=Decision.ROLLBACK)

    await await_workflow_failed(wf_id)

    assert_call_log_order(
        call_log,
        [
            "execute:a",
            _Unordered(_Optional("execute:b"), "execute:failing"),
            _Unordered(_Optional("compensate:b"), "compensate:failing"),
            "compensate:a",
        ],
    )
    await assert_workflow_status(workflow_engine, wf_id, state=WorkflowState.FAILED, steps_total=3)


async def _assert_running_step(workflow_engine: WorkflowEngine, workflow_id: str, step_name: str) -> None:
    async for attempt in AsyncRetrying(wait=_POLL_WAIT, stop=_POLL_STOP, reraise=True):
        with attempt:
            status = await workflow_engine.status(workflow_id)
            assert step_name in status.running_activities
            assert status.state == WorkflowState.RUNNING


async def test_cancellation_during_running_activity(
    workflow_engine: WorkflowEngine,
    blocking_sequential_workflow: type[SagaWorkflow],
    call_log: list[str],
    log_key: str,
    await_workflow_failed: Callable[[str], Coroutine[Any, Any, None]],
):
    wf_id = "test-cancel-running"
    await workflow_engine.start(
        blocking_sequential_workflow.__name__,
        workflow_id=wf_id,
        context={"log_key": log_key},
    )

    # Wait until the blocking activity is in progress
    await _assert_running_step(workflow_engine, wf_id, "step_blocking")

    await workflow_engine.cancel(wf_id)

    await await_workflow_failed(wf_id)

    # The blocking activity was cancelled (infinite sleep interrupted).
    # Temporalio wraps the cancellation as ActivityError, so the engine's
    # ROLLBACK policy registers its compensation. All executed steps are undone.
    assert_call_log_order(
        call_log,
        ["execute:a", "execute:blocking", "compensate:blocking", "compensate:a"],
    )
    await assert_workflow_status(
        workflow_engine,
        wf_id,
        state=WorkflowState.FAILED,
        completed={"step_a"},
        failed={"step_blocking": ""},
        compensated={"undo_blocking", "undo_a"},
        steps_total=3,
    )


async def test_parallel_slow_activity_compensated_after_fast_failure(
    workflow_engine: WorkflowEngine,
    parallel_slow_fast_fail_workflow: type[SagaWorkflow],
    call_log: list[str],
    log_key: str,
    await_workflow_failed: Callable[[str], Coroutine[Any, Any, None]],
):
    wf_id = "test-parallel-slow-fail"
    await workflow_engine.start(
        parallel_slow_fast_fail_workflow.__name__,
        workflow_id=wf_id,
        context={"log_key": log_key},
    )

    await await_workflow_failed(wf_id)

    # The slow activity always completes (gather waits for all tasks),
    # so both slow and failing MUST appear — no _Optional here.
    assert_call_log_order(
        call_log,
        [
            "execute:a",
            _Unordered("execute:slow", "execute:failing"),
            _Unordered("compensate:slow", "compensate:failing"),
            "compensate:a",
        ],
    )
    await assert_workflow_status(
        workflow_engine,
        wf_id,
        state=WorkflowState.FAILED,
        completed={"step_a", "step_slow"},
        failed={"step_failing": ""},
        compensated={"undo_slow", "undo_failing", "undo_a"},
        steps_total=3,
    )


async def test_progress_tracking(
    workflow_engine: WorkflowEngine,
    parallel_workflow: type[SagaWorkflow],
    call_log: list[str],
    log_key: str,
    await_workflow_completed: Callable[[str], Coroutine[Any, Any, dict[str, Any]]],
):
    """ParallelWorkflow has step_a followed by Parallel(step_b, step_c) -> 3 total steps."""
    wf_id = "test-progress"
    await workflow_engine.start(
        parallel_workflow.__name__,
        workflow_id=wf_id,
        context={"log_key": log_key},
    )

    await await_workflow_completed(wf_id)

    status = await workflow_engine.status(wf_id)
    assert status.steps_total == 3
    assert len(status.completed_activities) == 3
    assert status.completed_activities == {"step_a", "step_b", "step_c"}
    assert status.failed_activities == {}
    assert status.compensated_activities == set()
    assert status.progress_percent == pytest.approx(1.0)
    assert status.running_activities == set()
    assert status.state == WorkflowState.COMPLETED
    await assert_workflow_status(
        workflow_engine,
        wf_id,
        state=WorkflowState.COMPLETED,
        completed={"step_a", "step_b", "step_c"},
        failed={},
        compensated=set(),
        steps_total=3,
        progress=1.0,
    )


async def test_progress_tracking_during_execution(
    workflow_engine: WorkflowEngine,
    blocking_sequential_workflow: type[SagaWorkflow],
    call_log: list[str],
    log_key: str,
    await_workflow_failed: Callable[[str], Coroutine[Any, Any, None]],
):
    """BlockingSequentialWorkflow: a -> blocking(inf) -> c -> 3 total steps.

    Query progress while blocked on 2nd step to verify intermediate values.
    """
    wf_id = "test-progress-mid"
    await workflow_engine.start(
        blocking_sequential_workflow.__name__,
        workflow_id=wf_id,
        context={"log_key": log_key},
    )

    await _assert_running_step(workflow_engine, wf_id, "step_blocking")

    status = await workflow_engine.status(wf_id)
    assert status.steps_total == 3
    assert status.completed_activities == {"step_a"}
    assert status.failed_activities == {}
    assert status.progress_percent == pytest.approx(1 / 3)
    assert "step_blocking" in status.running_activities

    await workflow_engine.cancel(wf_id)
    await await_workflow_failed(wf_id)

    final = await workflow_engine.status(wf_id)
    assert "step_blocking" in final.failed_activities
    assert len(final.compensated_activities) > 0
    await assert_workflow_status(
        workflow_engine,
        wf_id,
        state=WorkflowState.FAILED,
        completed={"step_a"},
        failed={"step_blocking": ""},
        steps_total=3,
    )


async def test_parallel_double_fail_skip_one_rollback_other(
    workflow_engine: WorkflowEngine,
    parallel_double_fail_workflow: type[SagaWorkflow],
    call_log: list[str],
    log_key: str,
    await_workflow_failed: Callable[[str], Coroutine[Any, Any, None]],
):
    """Two activities fail in the same parallel group.
    Skip the first, rollback the second — verify per-activity control works."""
    wf_id = "test-double-fail-skip-rollback"
    await workflow_engine.start(
        parallel_double_fail_workflow.__name__,
        workflow_id=wf_id,
        context={"log_key": log_key},
    )

    await _assert_state_waiting_intervention(workflow_engine, wf_id)

    # Both activities should be in failed_activities
    status = await workflow_engine.status(wf_id)
    assert "step_failing" in status.failed_activities
    assert "step_failing_b" in status.failed_activities

    # Skip one, rollback the other
    await workflow_engine.signal(wf_id, activity_name="step_failing", decision=Decision.SKIP)
    await workflow_engine.signal(wf_id, activity_name="step_failing_b", decision=Decision.ROLLBACK)

    await await_workflow_failed(wf_id)

    assert_call_log_order(
        call_log,
        [
            "execute:a",
            _Unordered("execute:failing", "execute:failing_b"),
            _Unordered("compensate:failing_b", _Optional("compensate:failing")),
            "compensate:a",
        ],
        skipped_activities={"failing"},
    )
    await assert_workflow_status(workflow_engine, wf_id, state=WorkflowState.FAILED, steps_total=3)


async def test_parallel_double_fail_skip_both(
    workflow_engine: WorkflowEngine,
    parallel_double_fail_workflow: type[SagaWorkflow],
    call_log: list[str],
    log_key: str,
    await_workflow_completed: Callable[[str], Coroutine[Any, Any, dict[str, Any]]],
):
    """Two activities fail in the same parallel group.
    Skip both — workflow should complete successfully."""
    wf_id = "test-double-fail-skip-both"
    await workflow_engine.start(
        parallel_double_fail_workflow.__name__,
        workflow_id=wf_id,
        context={"log_key": log_key},
    )

    await _assert_state_waiting_intervention(workflow_engine, wf_id)

    await workflow_engine.signal(wf_id, activity_name="step_failing", decision=Decision.SKIP)
    await workflow_engine.signal(wf_id, activity_name="step_failing_b", decision=Decision.SKIP)

    result = await await_workflow_completed(wf_id)
    assert result.get("a_result") == "done_a"

    assert_call_log_order(
        call_log,
        [
            "execute:a",
            _Unordered("execute:failing", "execute:failing_b"),
        ],
    )
    await assert_workflow_status(
        workflow_engine,
        wf_id,
        state=WorkflowState.COMPLETED,
        completed={"step_a"},
        failed={},
        compensated=set(),
        skipped={"step_failing", "step_failing_b"},
        steps_total=3,
    )


async def test_parallel_double_fail_ignores_unknown_signal_and_rollbacks_both(
    workflow_engine: WorkflowEngine,
    parallel_double_fail_workflow: type[SagaWorkflow],
    app: FastAPI,
    call_log: list[str],
    log_key: str,
    await_workflow_failed: Callable[[str], Coroutine[Any, Any, None]],
    mocker: MockerFixture,
):
    """Unknown signal is ignored while waiting.

    Rolling back both parallel failures also triggers the secondary-failure warning.
    """

    warning_mock = mocker.patch(
        "simcore_service_dynamic_scheduler.services.t_scheduler._base_workflow.workflow.logger.warning"
    )

    wf_id = "test-double-fail-unknown-signal-rollback-both"
    await workflow_engine.start(
        parallel_double_fail_workflow.__name__,
        workflow_id=wf_id,
        context={"log_key": log_key},
    )

    await _assert_state_waiting_intervention(workflow_engine, wf_id)

    # Bypass WorkflowEngine validation to hit SagaWorkflow.resolve() unknown-signal branch.
    client = get_temporalio_client(app)
    handle = client.get_workflow_handle(wf_id)
    await handle.signal(
        "resolve",
        ResolutionSignal(activity_name="not_a_real_activity", decision=Decision.SKIP),
    )

    # Unknown signal must be ignored: workflow stays in waiting-intervention and both failures remain unresolved.
    await _assert_state_waiting_intervention(workflow_engine, wf_id)
    status = await workflow_engine.status(wf_id)
    assert "step_failing" in status.failed_activities
    assert "step_failing_b" in status.failed_activities

    # Resolve both failed activities as rollback; this creates two parallel failures.
    await workflow_engine.signal(wf_id, activity_name="step_failing", decision=Decision.ROLLBACK)
    await workflow_engine.signal(wf_id, activity_name="step_failing_b", decision=Decision.ROLLBACK)

    await await_workflow_failed(wf_id)

    warning_messages = [call.args[0] for call in warning_mock.call_args_list if call.args]
    assert any("Ignoring signal for" in message for message in warning_messages)
    assert any("Parallel activity %s also failed" in message for message in warning_messages)

    assert_call_log_order(
        call_log,
        [
            "execute:a",
            _Unordered("execute:failing", "execute:failing_b"),
            _Unordered(_Optional("compensate:failing"), _Optional("compensate:failing_b")),
            "compensate:a",
        ],
    )


async def test_parallel_manual_intervention_retry(
    workflow_engine: WorkflowEngine,
    parallel_manual_intervention_workflow: type[SagaWorkflow],
    call_log: list[str],
    log_key: str,
    await_workflow_completed: Callable[[str], Coroutine[Any, Any, dict[str, Any]]],
):
    """Retry a failed activity in a parallel group, then skip to complete."""
    wf_id = "test-parallel-retry"
    await workflow_engine.start(
        parallel_manual_intervention_workflow.__name__,
        workflow_id=wf_id,
        context={"log_key": log_key},
    )

    await _assert_state_waiting_intervention(workflow_engine, wf_id)

    # Retry — activity always fails, so we'll be back at waiting_intervention
    await workflow_engine.signal(wf_id, activity_name="step_failing", decision=Decision.RETRY)
    await _assert_state_waiting_intervention(workflow_engine, wf_id)

    # Now skip to let it finish
    await workflow_engine.signal(wf_id, activity_name="step_failing", decision=Decision.SKIP)

    result = await await_workflow_completed(wf_id)
    assert result.get("a_result") == "done_a"
    assert result.get("b_result") == "done_b"

    assert_call_log_order(
        call_log,
        [
            "execute:a",
            _Unordered("execute:b", "execute:failing"),
            "execute:failing",
        ],
    )
    await assert_workflow_status(
        workflow_engine,
        wf_id,
        state=WorkflowState.COMPLETED,
        completed={"step_a", "step_b"},
        failed={},
        compensated=set(),
        skipped={"step_failing"},
        steps_total=3,
    )


async def test_parallel_double_fail_retry_both(
    workflow_engine: WorkflowEngine,
    parallel_double_fail_workflow: type[SagaWorkflow],
    call_log: list[str],
    log_key: str,
    await_workflow_completed: Callable[[str], Coroutine[Any, Any, dict[str, Any]]],
):
    """Two failures in parallel, retry both, then skip both."""
    wf_id = "test-double-fail-retry-both"
    await workflow_engine.start(
        parallel_double_fail_workflow.__name__,
        workflow_id=wf_id,
        context={"log_key": log_key},
    )

    await _assert_state_waiting_intervention(workflow_engine, wf_id)

    # Retry both — they will fail again
    await workflow_engine.signal(wf_id, activity_name="step_failing", decision=Decision.RETRY)
    await workflow_engine.signal(wf_id, activity_name="step_failing_b", decision=Decision.RETRY)

    await _assert_state_waiting_intervention(workflow_engine, wf_id)

    # Now skip both
    await workflow_engine.signal(wf_id, activity_name="step_failing", decision=Decision.SKIP)
    await workflow_engine.signal(wf_id, activity_name="step_failing_b", decision=Decision.SKIP)

    result = await await_workflow_completed(wf_id)
    assert result.get("a_result") == "done_a"

    # Each activity is executed twice (initial + retry)
    assert_call_log_order(
        call_log,
        [
            "execute:a",
            _Unordered("execute:failing", "execute:failing_b"),
            _Unordered("execute:failing", "execute:failing_b"),
        ],
    )
    await assert_workflow_status(
        workflow_engine,
        wf_id,
        state=WorkflowState.COMPLETED,
        completed={"step_a"},
        failed={},
        compensated=set(),
        skipped={"step_failing", "step_failing_b"},
        steps_total=3,
    )


async def test_compensation_failure_continues(
    workflow_engine: WorkflowEngine,
    compensation_failure_workflow: type[SagaWorkflow],
    call_log: list[str],
    log_key: str,
    await_workflow_failed: Callable[[str], Coroutine[Any, Any, None]],
):
    """When an undo activity fails, compensation continues with remaining steps.

    CompensationFailureWorkflow: a -> b(undo=broken) -> failing(ROLLBACK).
    undo_broken raises, but undo_a should still execute.
    """
    wf_id = "test-compensation-failure"
    await workflow_engine.start(
        compensation_failure_workflow.__name__,
        workflow_id=wf_id,
        context={"log_key": log_key},
    )

    await await_workflow_failed(wf_id)

    # undo_broken always fails; compensation retries it 3 times
    # (RetryPolicy maximum_attempts=3), then moves on to undo_a.
    assert_call_log_order(
        call_log,
        [
            "execute:a",
            "execute:b",
            "execute:failing",
            "compensate:failing",
            *["compensate:broken_undo"] * 3,
            "compensate:a",
        ],
        skipped_activities={"b"},
    )

    await assert_workflow_status(
        workflow_engine,
        wf_id,
        state=WorkflowState.FAILED,
        completed={"step_a", "step_b"},
        failed={"step_failing": ""},
        compensated={"undo_failing", "undo_a"},
        failed_compensations={"undo_broken": ""},
        steps_total=3,
    )
    await assert_history_order(
        workflow_engine,
        wf_id,
        [
            ActivityStarted(activity_name="step_a"),
            ActivityCompleted(activity_name="step_a"),
            ActivityStarted(activity_name="step_b"),
            ActivityCompleted(activity_name="step_b"),
            ActivityStarted(activity_name="step_failing"),
            ActivityFailed(activity_name="step_failing"),
            StateChanged(new_state=WorkflowState.COMPENSATING),
            CompensationStarted(activity_name="undo_failing"),
            CompensationCompleted(activity_name="undo_failing"),
            CompensationStarted(activity_name="undo_broken"),
            CompensationFailed(activity_name="undo_broken"),
            CompensationStarted(activity_name="undo_a"),
            CompensationCompleted(activity_name="undo_a"),
            StateChanged(new_state=WorkflowState.FAILED),
        ],
    )
