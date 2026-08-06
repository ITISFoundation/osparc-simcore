import logging
from datetime import timedelta
from typing import Any

from temporalio import activity, workflow
from temporalio.common import RetryPolicy

from ..t_scheduler._base_workflow import SagaWorkflow
from ..t_scheduler._models import FailurePolicy, Step, StepSequence

_logger = logging.getLogger(__name__)


@activity.defn
async def healthcheck_activity(_ctx: dict[str, Any]) -> dict[str, Any]:
    _logger.info("Healthcheck activity executed")
    return {"healthcheck": "ok"}


@activity.defn
async def undo_healthcheck_activity(_ctx: dict[str, Any]) -> None:
    _logger.info("Healthcheck activity compensated (no-op)")


@workflow.defn(sandboxed=False)
class HealthcheckWorkflow(SagaWorkflow):
    """Minimal workflow used to validate the Temporal worker is operational."""

    def steps(self) -> StepSequence:
        return (
            Step(
                fn=healthcheck_activity,
                undo=undo_healthcheck_activity,
                retry=RetryPolicy(maximum_attempts=1),
                timeout=timedelta(seconds=10),
                on_failure=FailurePolicy.ROLLBACK,
            ),
        )

    @workflow.run
    async def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        return await self._run_saga(input_data)
