# pylint:disable=protected-access
# pylint:disable=redefined-outer-name
# pylint:disable=too-many-arguments
# pylint:disable=unused-argument

import asyncio
from collections.abc import AsyncIterator, Iterable
from datetime import timedelta
from typing import Any, Final

import pytest
from fastapi import FastAPI
from pytest_mock import MockerFixture
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_service_dynamic_scheduler.core.settings import ApplicationSettings
from simcore_service_dynamic_scheduler.services.t_scheduler._base_workflow import (
    SagaWorkflow,
)
from simcore_service_dynamic_scheduler.services.t_scheduler._models import (
    FailurePolicy,
    Parallel,
    Step,
    StepSequence,
)
from simcore_service_dynamic_scheduler.services.t_scheduler._registry import (
    WorkflowRegistry,
)
from temporalio import activity, workflow
from temporalio.common import RetryPolicy
from temporalio.testing import WorkflowEnvironment

_DEFAULT_RETRY = RetryPolicy(maximum_attempts=1)
_DEFAULT_TIMEOUT = timedelta(seconds=10)

_WORKFLOWS_MODULE: Final[str] = "simcore_service_dynamic_scheduler.services.workflows"

# ── shared call log ──────────────────────────────────────────────────
# Each test gets its own call log keyed by a faker-generated ``log_key``
# that is passed inside the workflow context dict.  Activities read
# ``ctx["log_key"]`` to record entries, making parallel test execution
# (pytest-xdist) safe without any global mutable state.

_call_logs: dict[str, list[str]] = {}


def _record_call(log_key: str, entry: str) -> None:
    _call_logs[log_key].append(entry)


@pytest.fixture
def log_key(faker) -> str:
    return faker.uuid4()


@pytest.fixture
def call_log(log_key: str) -> Iterable[list[str]]:
    _call_logs[log_key] = []
    yield _call_logs[log_key]
    _call_logs.pop(log_key, None)


# ── activity implementations ─────────────────────────────────────────


async def _step_impl(ctx: dict[str, Any], name: str) -> dict[str, Any]:
    _record_call(ctx["log_key"], f"execute:{name}")
    return {f"{name}_result": f"done_{name}"}


async def _failing_impl(ctx: dict[str, Any], name: str) -> dict[str, Any]:
    _record_call(ctx["log_key"], f"execute:{name}")
    msg = "Activity failed intentionally"
    raise RuntimeError(msg)


async def _undo_impl(ctx: dict[str, Any], name: str) -> None:
    _record_call(ctx["log_key"], f"compensate:{name}")


async def _slow_step_impl(ctx: dict[str, Any], name: str, *, delay: float = 1.0) -> dict[str, Any]:
    _record_call(ctx["log_key"], f"execute:{name}")
    await asyncio.sleep(delay)
    return {f"{name}_result": f"done_{name}"}


async def _broken_undo_impl(ctx: dict[str, Any], name: str) -> None:
    _record_call(ctx["log_key"], f"compensate:{name}")
    msg = "Undo failed intentionally"
    raise RuntimeError(msg)


# ── activity definitions ────────────────────────────────────────────


@activity.defn
async def step_a(ctx: dict[str, Any]) -> dict[str, Any]:
    return await _step_impl(ctx, "a")


@activity.defn
async def undo_a(result: dict[str, Any]) -> None:
    await _undo_impl(result, "a")


@activity.defn
async def step_b(ctx: dict[str, Any]) -> dict[str, Any]:
    return await _step_impl(ctx, "b")


@activity.defn
async def undo_b(result: dict[str, Any]) -> None:
    await _undo_impl(result, "b")


@activity.defn
async def step_c(ctx: dict[str, Any]) -> dict[str, Any]:
    return await _step_impl(ctx, "c")


@activity.defn
async def undo_c(result: dict[str, Any]) -> None:
    await _undo_impl(result, "c")


@activity.defn
async def step_failing(ctx: dict[str, Any]) -> dict[str, Any]:
    return await _failing_impl(ctx, "failing")


@activity.defn
async def undo_failing(result: dict[str, Any]) -> None:
    await _undo_impl(result, "failing")


@activity.defn
async def step_slow(ctx: dict[str, Any]) -> dict[str, Any]:
    return await _slow_step_impl(ctx, "slow")


@activity.defn
async def undo_slow(result: dict[str, Any]) -> None:
    await _undo_impl(result, "slow")


@activity.defn
async def step_blocking(ctx: dict[str, Any]) -> dict[str, Any]:
    return await _slow_step_impl(ctx, "blocking", delay=float("inf"))


@activity.defn
async def undo_blocking(result: dict[str, Any]) -> None:
    await _undo_impl(result, "blocking")


@activity.defn
async def step_failing_b(ctx: dict[str, Any]) -> dict[str, Any]:
    return await _failing_impl(ctx, "failing_b")


@activity.defn
async def undo_failing_b(result: dict[str, Any]) -> None:
    await _undo_impl(result, "failing_b")


@activity.defn
async def undo_broken(result: dict[str, Any]) -> None:
    await _broken_undo_impl(result, "broken_undo")


# ── test workflows ──────────────────────────────────────────────────


@workflow.defn(sandboxed=False)
class HappyPathWorkflow(SagaWorkflow):
    def steps(self) -> StepSequence:
        return (
            Step(fn=step_a, undo=undo_a, retry=_DEFAULT_RETRY, timeout=_DEFAULT_TIMEOUT),
            Step(fn=step_b, undo=undo_b, retry=_DEFAULT_RETRY, timeout=_DEFAULT_TIMEOUT),
            Step(fn=step_c, undo=undo_c, retry=_DEFAULT_RETRY, timeout=_DEFAULT_TIMEOUT),
        )

    @workflow.run
    async def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        return await self._run_saga(input_data)


@workflow.defn(sandboxed=False)
class AutoRollbackWorkflow(SagaWorkflow):
    def steps(self) -> StepSequence:
        return (
            Step(fn=step_a, undo=undo_a, retry=_DEFAULT_RETRY, timeout=_DEFAULT_TIMEOUT),
            Step(fn=step_b, undo=undo_b, retry=_DEFAULT_RETRY, timeout=_DEFAULT_TIMEOUT),
            Step(
                fn=step_failing,
                undo=undo_failing,
                retry=_DEFAULT_RETRY,
                timeout=_DEFAULT_TIMEOUT,
                on_failure=FailurePolicy.ROLLBACK,
            ),
        )

    @workflow.run
    async def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        return await self._run_saga(input_data)


@workflow.defn(sandboxed=False)
class ManualInterventionWorkflow(SagaWorkflow):
    def steps(self) -> StepSequence:
        return (
            Step(fn=step_a, undo=undo_a, retry=_DEFAULT_RETRY, timeout=_DEFAULT_TIMEOUT),
            Step(
                fn=step_failing,
                undo=undo_failing,
                retry=_DEFAULT_RETRY,
                timeout=_DEFAULT_TIMEOUT,
                on_failure=FailurePolicy.MANUAL_INTERVENTION,
            ),
            Step(fn=step_c, undo=undo_c, retry=_DEFAULT_RETRY, timeout=_DEFAULT_TIMEOUT),
        )

    @workflow.run
    async def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        return await self._run_saga(input_data)


@workflow.defn(sandboxed=False)
class ParallelWorkflow(SagaWorkflow):
    def steps(self) -> StepSequence:
        return (
            Step(fn=step_a, undo=undo_a, retry=_DEFAULT_RETRY, timeout=_DEFAULT_TIMEOUT),
            Parallel(
                [
                    Step(fn=step_b, undo=undo_b, retry=_DEFAULT_RETRY, timeout=_DEFAULT_TIMEOUT),
                    Step(fn=step_c, undo=undo_c, retry=_DEFAULT_RETRY, timeout=_DEFAULT_TIMEOUT),
                ]
            ),
        )

    @workflow.run
    async def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        return await self._run_saga(input_data)


@workflow.defn(sandboxed=False)
class ParallelAutoRollbackWorkflow(SagaWorkflow):
    def steps(self) -> StepSequence:
        return (
            Step(fn=step_a, undo=undo_a, retry=_DEFAULT_RETRY, timeout=_DEFAULT_TIMEOUT),
            Parallel(
                [
                    Step(fn=step_b, undo=undo_b, retry=_DEFAULT_RETRY, timeout=_DEFAULT_TIMEOUT),
                    Step(
                        fn=step_failing,
                        undo=undo_failing,
                        retry=_DEFAULT_RETRY,
                        timeout=_DEFAULT_TIMEOUT,
                        on_failure=FailurePolicy.ROLLBACK,
                    ),
                ]
            ),
        )

    @workflow.run
    async def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        return await self._run_saga(input_data)


@workflow.defn(sandboxed=False)
class ParallelManualInterventionWorkflow(SagaWorkflow):
    def steps(self) -> StepSequence:
        return (
            Step(fn=step_a, undo=undo_a, retry=_DEFAULT_RETRY, timeout=_DEFAULT_TIMEOUT),
            Parallel(
                [
                    Step(fn=step_b, undo=undo_b, retry=_DEFAULT_RETRY, timeout=_DEFAULT_TIMEOUT),
                    Step(
                        fn=step_failing,
                        undo=undo_failing,
                        retry=_DEFAULT_RETRY,
                        timeout=_DEFAULT_TIMEOUT,
                        on_failure=FailurePolicy.MANUAL_INTERVENTION,
                    ),
                ]
            ),
        )

    @workflow.run
    async def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        return await self._run_saga(input_data)


@workflow.defn(sandboxed=False)
class SlowSequentialWorkflow(SagaWorkflow):
    def steps(self) -> StepSequence:
        return (
            Step(fn=step_a, undo=undo_a, retry=_DEFAULT_RETRY, timeout=_DEFAULT_TIMEOUT),
            Step(fn=step_slow, undo=undo_slow, retry=_DEFAULT_RETRY, timeout=_DEFAULT_TIMEOUT),
            Step(fn=step_c, undo=undo_c, retry=_DEFAULT_RETRY, timeout=_DEFAULT_TIMEOUT),
        )

    @workflow.run
    async def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        return await self._run_saga(input_data)


@workflow.defn(sandboxed=False)
class BlockingSequentialWorkflow(SagaWorkflow):
    def steps(self) -> StepSequence:
        return (
            Step(fn=step_a, undo=undo_a, retry=_DEFAULT_RETRY, timeout=_DEFAULT_TIMEOUT),
            Step(fn=step_blocking, undo=undo_blocking, retry=_DEFAULT_RETRY, timeout=timedelta(days=30)),
            Step(fn=step_c, undo=undo_c, retry=_DEFAULT_RETRY, timeout=_DEFAULT_TIMEOUT),
        )

    @workflow.run
    async def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        return await self._run_saga(input_data)


@workflow.defn(sandboxed=False)
class ParallelSlowFastFailWorkflow(SagaWorkflow):
    def steps(self) -> StepSequence:
        return (
            Step(fn=step_a, undo=undo_a, retry=_DEFAULT_RETRY, timeout=_DEFAULT_TIMEOUT),
            Parallel(
                [
                    Step(fn=step_slow, undo=undo_slow, retry=_DEFAULT_RETRY, timeout=_DEFAULT_TIMEOUT),
                    Step(
                        fn=step_failing,
                        undo=undo_failing,
                        retry=_DEFAULT_RETRY,
                        timeout=_DEFAULT_TIMEOUT,
                        on_failure=FailurePolicy.ROLLBACK,
                    ),
                ]
            ),
        )

    @workflow.run
    async def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        return await self._run_saga(input_data)


@workflow.defn(sandboxed=False)
class ParallelDoubleFailWorkflow(SagaWorkflow):
    def steps(self) -> StepSequence:
        return (
            Step(fn=step_a, undo=undo_a, retry=_DEFAULT_RETRY, timeout=_DEFAULT_TIMEOUT),
            Parallel(
                [
                    Step(
                        fn=step_failing,
                        undo=undo_failing,
                        retry=_DEFAULT_RETRY,
                        timeout=_DEFAULT_TIMEOUT,
                        on_failure=FailurePolicy.MANUAL_INTERVENTION,
                    ),
                    Step(
                        fn=step_failing_b,
                        undo=undo_failing_b,
                        retry=_DEFAULT_RETRY,
                        timeout=_DEFAULT_TIMEOUT,
                        on_failure=FailurePolicy.MANUAL_INTERVENTION,
                    ),
                ]
            ),
        )

    @workflow.run
    async def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        return await self._run_saga(input_data)


@workflow.defn(sandboxed=False)
class CompensationFailureWorkflow(SagaWorkflow):
    def steps(self) -> StepSequence:
        return (
            Step(fn=step_a, undo=undo_a, retry=_DEFAULT_RETRY, timeout=_DEFAULT_TIMEOUT),
            Step(fn=step_b, undo=undo_broken, retry=_DEFAULT_RETRY, timeout=_DEFAULT_TIMEOUT),
            Step(
                fn=step_failing,
                undo=undo_failing,
                retry=_DEFAULT_RETRY,
                timeout=_DEFAULT_TIMEOUT,
                on_failure=FailurePolicy.ROLLBACK,
            ),
        )

    @workflow.run
    async def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        return await self._run_saga(input_data)


# ── fixtures ────────────────────────────────────────────────────────


@pytest.fixture
def happy_path_workflow() -> type[SagaWorkflow]:
    return HappyPathWorkflow


@pytest.fixture
def auto_rollback_workflow() -> type[SagaWorkflow]:
    return AutoRollbackWorkflow


@pytest.fixture
def manual_intervention_workflow() -> type[SagaWorkflow]:
    return ManualInterventionWorkflow


@pytest.fixture
def parallel_workflow() -> type[SagaWorkflow]:
    return ParallelWorkflow


@pytest.fixture
def parallel_auto_rollback_workflow() -> type[SagaWorkflow]:
    return ParallelAutoRollbackWorkflow


@pytest.fixture
def parallel_manual_intervention_workflow() -> type[SagaWorkflow]:
    return ParallelManualInterventionWorkflow


@pytest.fixture
def slow_sequential_workflow() -> type[SagaWorkflow]:
    return SlowSequentialWorkflow


@pytest.fixture
def parallel_slow_fast_fail_workflow() -> type[SagaWorkflow]:
    return ParallelSlowFastFailWorkflow


@pytest.fixture
def blocking_sequential_workflow() -> type[SagaWorkflow]:
    return BlockingSequentialWorkflow


@pytest.fixture
def parallel_double_fail_workflow() -> type[SagaWorkflow]:
    return ParallelDoubleFailWorkflow


@pytest.fixture
def compensation_failure_workflow() -> type[SagaWorkflow]:
    return CompensationFailureWorkflow


@pytest.fixture
def all_test_workflow_classes(
    happy_path_workflow: type[SagaWorkflow],
    auto_rollback_workflow: type[SagaWorkflow],
    manual_intervention_workflow: type[SagaWorkflow],
    parallel_workflow: type[SagaWorkflow],
    parallel_auto_rollback_workflow: type[SagaWorkflow],
    parallel_manual_intervention_workflow: type[SagaWorkflow],
    slow_sequential_workflow: type[SagaWorkflow],
    parallel_slow_fast_fail_workflow: type[SagaWorkflow],
    blocking_sequential_workflow: type[SagaWorkflow],
    parallel_double_fail_workflow: type[SagaWorkflow],
    compensation_failure_workflow: type[SagaWorkflow],
) -> list[type[SagaWorkflow]]:
    return [
        happy_path_workflow,
        auto_rollback_workflow,
        manual_intervention_workflow,
        parallel_workflow,
        parallel_auto_rollback_workflow,
        parallel_manual_intervention_workflow,
        slow_sequential_workflow,
        parallel_slow_fast_fail_workflow,
        blocking_sequential_workflow,
        parallel_double_fail_workflow,
        compensation_failure_workflow,
    ]


@pytest.fixture
async def temporalio_server() -> AsyncIterator[WorkflowEnvironment]:
    async with await WorkflowEnvironment.start_local() as env:
        yield env


@pytest.fixture
def register_test_workflows(
    mocker: MockerFixture,
    all_test_workflow_classes: list[type[SagaWorkflow]],
) -> None:
    def _register_workflows(registry: WorkflowRegistry) -> None:
        for wf_cls in all_test_workflow_classes:
            registry.register(name=wf_cls.__name__, workflow_cls=wf_cls)

    mocker.patch(f"{_WORKFLOWS_MODULE}._lifespan._register_workflows", new=_register_workflows)


@pytest.fixture
async def app_environment(
    temporalio_server: WorkflowEnvironment,
    register_test_workflows: None,
    disable_postgres_lifespan: None,
    disable_rabbitmq_lifespan: None,
    disable_redis_lifespan: None,
    disable_service_tracker_lifespan: None,
    disable_deferred_manager_lifespan: None,
    disable_notifier_lifespan: None,
    disable_status_monitor_lifespan: None,
    monkeypatch: pytest.MonkeyPatch,
    app_environment: EnvVarsDict,
) -> EnvVarsDict:
    target = temporalio_server.client.service_client.config.target_host
    host, port_str = target.rsplit(":", 1)
    envs = setenvs_from_dict(
        monkeypatch,
        {
            "TEMPORALIO_HOST": host,
            "TEMPORALIO_PORT": port_str,
        },
    )
    return {**app_environment, **envs}


@pytest.fixture
def task_queue(app: FastAPI) -> str:
    settings: ApplicationSettings = app.state.settings
    return settings.DYNAMIC_SCHEDULER_TEMPORALIO_SETTINGS.TEMPORALIO_TASK_QUEUE
