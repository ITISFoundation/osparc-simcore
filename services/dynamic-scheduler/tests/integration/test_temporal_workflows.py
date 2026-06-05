# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument
# pylint:disable=protected-access

"""End-to-end integration tests for Temporal workflows.

These tests exercise the full stack — real Temporal server (via Docker Swarm),
real gRPC, real Worker, real saga compensation — through the public API
(``WorkflowEngine`` + REST ops endpoints).

Focus: catching regressions that escape unit tests during upgrades or
feature changes.
"""

import asyncio
import contextlib
import uuid
from typing import Any

import pytest
from httpx import AsyncClient
from simcore_service_dynamic_scheduler.services.t_scheduler import (
    WorkflowEngine,
)
from simcore_service_dynamic_scheduler.services.t_scheduler._models import (
    Decision,
    WorkflowState,
    WorkflowStatus,
)
from temporalio.client import WorkflowFailureError
from tenacity import AsyncRetrying, stop_after_delay, wait_fixed

pytest_simcore_core_services_selection = [
    "migration",
    "postgres",
    "rabbit",
    "redis",
    "temporal",
]
pytest_simcore_ops_services_selection = [
    "temporal-ui",
]


# ── helpers ───────────────────────────────────────────────────────────


async def _poll_status(
    engine: WorkflowEngine,
    workflow_id: str,
    *,
    target_state: WorkflowState,
    timeout_s: float = 30,
    poll_interval_s: float = 0.5,
) -> WorkflowStatus:
    """Poll ``engine.status()`` until the workflow reaches *target_state*."""
    status: WorkflowStatus | None = None

    async for attempt in AsyncRetrying(
        stop=stop_after_delay(timeout_s),
        wait=wait_fixed(poll_interval_s),
        reraise=True,
    ):
        with attempt:
            status = await engine.status(workflow_id)
            assert status.state == target_state, (
                f"Expected {target_state}, got {status.state} "
                f"(running={status.running_activities}, "
                f"failed={status.failed_activities})"
            )

    assert status is not None
    return status


async def _await_workflow_result(
    engine: WorkflowEngine,
    workflow_id: str,
    *,
    timeout_s: float = 30,
) -> dict[str, Any]:
    """Wait for a workflow to complete and return its result."""
    client = engine._client  # noqa: SLF001
    handle = client.get_workflow_handle(workflow_id)
    return await asyncio.wait_for(handle.result(), timeout=timeout_s)


async def _await_no_running_workflows(
    engine: WorkflowEngine,
    workflow_ids: set[str],
    *,
    timeout_s: float = 10,
    poll_interval_s: float = 0.5,
) -> None:
    """Poll until the provided workflows disappear from Temporal's running list."""
    async for attempt in AsyncRetrying(
        stop=stop_after_delay(timeout_s),
        wait=wait_fixed(poll_interval_s),
        reraise=True,
    ):
        with attempt:
            running = await engine.list_running_workflows()
            running_ids = {wf.workflow_id for wf in running}
            still_running = workflow_ids & running_ids
            assert not still_running, f"Still reported as running: {sorted(still_running)}"


# ── tests ─────────────────────────────────────────────────────────────


async def test_ops_drain_before_redeploy(
    engine: WorkflowEngine,
    client: AsyncClient,
):
    """Simulate the ops shutdown path before a redeploy.

    Start several workflows (some fast, some stuck at MANUAL_INTERVENTION),
    drain via REST ops endpoints, and verify all workflows are cancelled.
    """
    # Start happy-path workflows (will complete quickly)
    run = uuid.uuid4().hex[:8]
    happy_ids = [f"ops-drain-happy-{run}-{i}" for i in range(3)]
    for wf_id in happy_ids:
        await engine.start(
            "HappyPathIntegrationWorkflow",
            workflow_id=wf_id,
            context={"workflow_id": wf_id},
        )

    # Start blocking workflows (stuck at MANUAL_INTERVENTION)
    stuck_ids = [f"ops-drain-stuck-{run}-{i}" for i in range(2)]
    for wf_id in stuck_ids:
        await engine.start(
            "BlockingInterventionWorkflow",
            workflow_id=wf_id,
            context={"workflow_id": wf_id},
        )

    # Wait for happy-path workflows to complete
    for wf_id in happy_ids:
        await _await_workflow_result(engine, wf_id, timeout_s=30)

    # Wait for stuck workflows to reach WAITING_INTERVENTION
    for wf_id in stuck_ids:
        await _poll_status(engine, wf_id, target_state=WorkflowState.WAITING_INTERVENTION)

    # REST: list running workflows — stuck ones should appear
    resp = await client.get("/v1/ops/temporalio-workflows")
    assert resp.status_code == 200
    running = resp.json()
    running_ids = {wf["workflow_id"] for wf in running}
    for wf_id in stuck_ids:
        assert wf_id in running_ids, f"{wf_id} should be in running list"

    # REST: cancel all running workflows
    resp = await client.post("/v1/ops/temporalio-workflows:shutdown")
    assert resp.status_code == 200
    data = resp.json()
    assert data["cancelled"] >= len(stuck_ids)

    # Wait for cancelled workflows to terminate (raise CancelledError internally)
    for wf_id in stuck_ids:
        handle = engine._client.get_workflow_handle(wf_id)  # noqa: SLF001
        with contextlib.suppress(WorkflowFailureError, asyncio.CancelledError):
            await asyncio.wait_for(handle.result(), timeout=30)

    # REST: verify our stuck workflows are no longer running
    resp = await client.get("/v1/ops/temporalio-workflows")
    assert resp.status_code == 200
    remaining_ids = {wf["workflow_id"] for wf in resp.json()}
    for wf_id in stuck_ids:
        assert wf_id not in remaining_ids, f"{wf_id} should have been cancelled"


async def test_mixed_sequential_parallel_workflow(
    engine: WorkflowEngine,
):
    """Workflow with step_a → Parallel(step_b, step_c) → step_d.

    Verify all activity results are merged into the context and the
    workflow completes with correct progress.
    """
    wf_id = f"mixed-seq-par-{uuid.uuid4().hex[:8]}"
    await engine.start(
        "MixedSequentialParallelWorkflow",
        workflow_id=wf_id,
        context={"workflow_id": wf_id},
    )

    result = await _await_workflow_result(engine, wf_id)

    # All activities contribute their result to the context
    assert result["a_result"] == "done_a"
    assert result["b_result"] == "done_b"
    assert result["c_result"] == "done_c"
    assert result["d_result"] == "done_d"

    # Status should show COMPLETED with full progress
    status = await engine.status(wf_id)
    assert status.state == WorkflowState.COMPLETED
    assert status.progress_percent == pytest.approx(1.0)
    assert status.completed_activities == {
        "integ_step_a",
        "integ_step_b",
        "integ_step_c",
        "integ_step_d",
    }
    assert status.failed_activities == {}
    assert status.skipped_activities == set()

    # Verify event ordering in history
    history = await engine.history(wf_id)
    event_names = [(e.kind, getattr(e, "activity_name", None) or getattr(e, "new_state", None)) for e in history.events]
    # step_a must start before parallel group
    a_started_idx = next(i for i, (k, n) in enumerate(event_names) if k == "activity_started" and n == "integ_step_a")
    a_completed_idx = next(
        i for i, (k, n) in enumerate(event_names) if k == "activity_completed" and n == "integ_step_a"
    )
    # step_d must start after parallel group
    d_started_idx = next(i for i, (k, n) in enumerate(event_names) if k == "activity_started" and n == "integ_step_d")
    assert a_started_idx < a_completed_idx < d_started_idx


async def test_stuck_workflows_skip_and_retry(
    engine: WorkflowEngine,
):
    """Workflow with two MANUAL_INTERVENTION steps: one retried, one skipped.

    step_flaky fails on first attempt → signal RETRY → succeeds on 2nd attempt.
    step_always_fail always fails → signal SKIP → workflow continues.
    """
    wf_id = f"stuck-skip-retry-{uuid.uuid4().hex[:8]}"
    await engine.start(
        "StuckMultiStepWorkflow",
        workflow_id=wf_id,
        context={"workflow_id": wf_id},
    )

    # Wait for step_flaky to fail and enter WAITING_INTERVENTION
    status = await _poll_status(engine, wf_id, target_state=WorkflowState.WAITING_INTERVENTION)
    assert "integ_step_flaky" in status.failed_activities

    # Signal RETRY for the flaky step — it will succeed on the 2nd attempt
    await engine.signal(wf_id, activity_name="integ_step_flaky", decision=Decision.RETRY)

    # Wait for step_always_fail to also hit WAITING_INTERVENTION
    status = await _poll_status(engine, wf_id, target_state=WorkflowState.WAITING_INTERVENTION)
    assert "integ_step_always_fail" in status.failed_activities

    # Signal SKIP for the always-failing step
    await engine.signal(wf_id, activity_name="integ_step_always_fail", decision=Decision.SKIP)

    # Workflow should now complete (step_c runs after the skipped step)
    result = await _await_workflow_result(engine, wf_id, timeout_s=30)

    # Verify final status
    status = await engine.status(wf_id)
    assert status.state == WorkflowState.COMPLETED
    assert "integ_step_flaky" in status.completed_activities
    assert "integ_step_always_fail" in status.skipped_activities
    assert "integ_step_a" in status.completed_activities
    assert "integ_step_c" in status.completed_activities

    # The flaky step returned a result after retry
    assert result["flaky_result"] == "done_flaky_after_retry"
    # step_c completed normally
    assert result["c_result"] == "done_c"


async def test_concurrent_workflow_burst(
    engine: WorkflowEngine,
):
    """Start many workflows simultaneously and verify all complete correctly.

    Validates the worker can handle concurrent load without race conditions.
    """
    n_workflows = 30
    run = uuid.uuid4().hex[:8]
    wf_ids = [f"burst-{run}-{i}" for i in range(n_workflows)]

    # Start all workflows concurrently
    await asyncio.gather(
        *(
            engine.start(
                "HappyPathIntegrationWorkflow",
                workflow_id=wf_id,
                context={"workflow_id": wf_id},
            )
            for wf_id in wf_ids
        )
    )

    # Await all results concurrently
    results = await asyncio.gather(*(_await_workflow_result(engine, wf_id, timeout_s=60) for wf_id in wf_ids))

    # All workflows should have produced the expected result
    for i, result in enumerate(results):
        assert result["a_result"] == "done_a", f"Workflow burst-{i} failed"
        assert result["b_result"] == "done_b", f"Workflow burst-{i} failed"
        assert result["c_result"] == "done_c", f"Workflow burst-{i} failed"

    # Temporal workflow listing is eventually consistent, so poll until our burst workflows disappear.
    await _await_no_running_workflows(engine, set(wf_ids))
