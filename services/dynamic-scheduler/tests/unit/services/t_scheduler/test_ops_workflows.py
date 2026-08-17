# pylint: disable=redefined-outer-name

import pytest
from fastapi import FastAPI
from simcore_service_dynamic_scheduler.services.t_scheduler import (
    WorkflowEngine,
    get_workflow_engine,
)
from simcore_service_dynamic_scheduler.services.t_scheduler._base_workflow import SagaWorkflow
from tenacity import AsyncRetrying, stop_after_delay, wait_fixed

_POLL_WAIT = wait_fixed(0.1)
_POLL_STOP = stop_after_delay(5)


@pytest.fixture
def workflow_engine(app: FastAPI) -> WorkflowEngine:
    return get_workflow_engine(app)


@pytest.fixture
def workflow_id() -> str:
    return "test-maintenance-window"


async def test_ops_maintenance_window_flow(
    workflow_engine: WorkflowEngine,
    blocking_sequential_workflow: type[SagaWorkflow],
    call_log: list[str],
    log_key: str,
    workflow_id: str,
):
    """Simulates the ops deployment flow:

    1. GET /ops/temporalio-workflows  → verify running workflow is visible
    2. POST /ops/temporalio-workflows:shutdown → cancel all, check count
    3. GET /ops/temporalio-workflows (poll) → wait until list is empty
    """
    await workflow_engine.start(
        blocking_sequential_workflow.__name__,
        workflow_id=workflow_id,
        context={"log_key": log_key},
    )

    # Wait until the blocking activity is executing (test setup)
    async for attempt in AsyncRetrying(wait=_POLL_WAIT, stop=_POLL_STOP, reraise=True):
        with attempt:
            status = await workflow_engine.status(workflow_id)
            assert "step_blocking" in status.running_activities

    # Step 1: ops queries running workflows
    running = await workflow_engine.list_running_workflows()
    workflow_ids = {wf.workflow_id for wf in running}
    assert workflow_id in workflow_ids

    # Step 2: ops triggers shutdown
    cancelled = await workflow_engine.cancel_all_workflows()
    assert cancelled == 1

    # Step 3: ops polls until all workflows have drained
    async for attempt in AsyncRetrying(wait=_POLL_WAIT, stop=_POLL_STOP, reraise=True):
        with attempt:
            remaining = await workflow_engine.list_running_workflows()
            assert len(remaining) == 0

    # Verify the full compensation sequence
    assert call_log == ["execute:a", "execute:blocking", "compensate:blocking", "compensate:a"]
