# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument

from collections.abc import AsyncIterator
from datetime import timedelta
from typing import Any, Final

import nicegui
import pytest
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pytest_mock import MockerFixture
from pytest_simcore.helpers.docker import get_service_published_port
from pytest_simcore.helpers.host import get_localhost_ip
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_service_dynamic_scheduler.core.application import create_app
from simcore_service_dynamic_scheduler.services.t_scheduler import (
    WorkflowEngine,
    WorkflowRegistry,
    get_workflow_engine,
)
from simcore_service_dynamic_scheduler.services.t_scheduler._base_workflow import (
    SagaWorkflow,
)
from simcore_service_dynamic_scheduler.services.t_scheduler._models import (
    FailurePolicy,
    Parallel,
    Step,
    StepSequence,
)
from simcore_service_dynamic_scheduler.services.workflows._lifespan import (
    _register_workflows as _register_production_workflows,
)
from temporalio import activity, workflow
from temporalio.common import RetryPolicy

_DEFAULT_RETRY = RetryPolicy(maximum_attempts=1)
_DEFAULT_TIMEOUT = timedelta(seconds=10)


# ── flaky activity state (keyed by workflow_id for thread safety) ────
_flaky_attempt_counts: dict[str, int] = {}


# ── activity implementations ─────────────────────────────────────────


async def _ok_impl(ctx: dict[str, Any], name: str) -> dict[str, Any]:
    return {f"{name}_result": f"done_{name}"}


async def _undo_impl(ctx: dict[str, Any], name: str) -> None:
    pass


async def _always_fail_impl(ctx: dict[str, Any], name: str) -> dict[str, Any]:
    msg = f"Activity {name} always fails"
    raise RuntimeError(msg)


async def _flaky_impl(ctx: dict[str, Any], name: str) -> dict[str, Any]:
    key = f"{ctx.get('workflow_id', 'unknown')}:{name}"
    _flaky_attempt_counts.setdefault(key, 0)
    _flaky_attempt_counts[key] += 1
    if _flaky_attempt_counts[key] < 2:
        msg = f"Activity {name} flaky failure (attempt {_flaky_attempt_counts[key]})"
        raise RuntimeError(msg)
    return {f"{name}_result": f"done_{name}_after_retry"}


# ── activity definitions ─────────────────────────────────────────────


@activity.defn
async def integ_step_a(ctx: dict[str, Any]) -> dict[str, Any]:
    return await _ok_impl(ctx, "a")


@activity.defn
async def integ_undo_a(ctx: dict[str, Any]) -> None:
    await _undo_impl(ctx, "a")


@activity.defn
async def integ_step_b(ctx: dict[str, Any]) -> dict[str, Any]:
    return await _ok_impl(ctx, "b")


@activity.defn
async def integ_undo_b(ctx: dict[str, Any]) -> None:
    await _undo_impl(ctx, "b")


@activity.defn
async def integ_step_c(ctx: dict[str, Any]) -> dict[str, Any]:
    return await _ok_impl(ctx, "c")


@activity.defn
async def integ_undo_c(ctx: dict[str, Any]) -> None:
    await _undo_impl(ctx, "c")


@activity.defn
async def integ_step_d(ctx: dict[str, Any]) -> dict[str, Any]:
    return await _ok_impl(ctx, "d")


@activity.defn
async def integ_undo_d(ctx: dict[str, Any]) -> None:
    await _undo_impl(ctx, "d")


@activity.defn
async def integ_step_flaky(ctx: dict[str, Any]) -> dict[str, Any]:
    return await _flaky_impl(ctx, "flaky")


@activity.defn
async def integ_undo_flaky(ctx: dict[str, Any]) -> None:
    await _undo_impl(ctx, "flaky")


@activity.defn
async def integ_step_always_fail(ctx: dict[str, Any]) -> dict[str, Any]:
    return await _always_fail_impl(ctx, "always_fail")


@activity.defn
async def integ_undo_always_fail(ctx: dict[str, Any]) -> None:
    await _undo_impl(ctx, "always_fail")


# ── test workflow definitions ─────────────────────────────────────────


@workflow.defn(sandboxed=False)
class HappyPathIntegrationWorkflow(SagaWorkflow):
    """step_a → step_b → step_c (all succeed)."""

    def steps(self) -> StepSequence:
        return (
            Step(fn=integ_step_a, undo=integ_undo_a, retry=_DEFAULT_RETRY, timeout=_DEFAULT_TIMEOUT),
            Step(fn=integ_step_b, undo=integ_undo_b, retry=_DEFAULT_RETRY, timeout=_DEFAULT_TIMEOUT),
            Step(fn=integ_step_c, undo=integ_undo_c, retry=_DEFAULT_RETRY, timeout=_DEFAULT_TIMEOUT),
        )

    @workflow.run
    async def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        return await self._run_saga(input_data)


@workflow.defn(sandboxed=False)
class MixedSequentialParallelWorkflow(SagaWorkflow):
    """step_a → Parallel(step_b, step_c) → step_d."""

    def steps(self) -> StepSequence:
        return (
            Step(fn=integ_step_a, undo=integ_undo_a, retry=_DEFAULT_RETRY, timeout=_DEFAULT_TIMEOUT),
            Parallel(
                [
                    Step(fn=integ_step_b, undo=integ_undo_b, retry=_DEFAULT_RETRY, timeout=_DEFAULT_TIMEOUT),
                    Step(fn=integ_step_c, undo=integ_undo_c, retry=_DEFAULT_RETRY, timeout=_DEFAULT_TIMEOUT),
                ]
            ),
            Step(fn=integ_step_d, undo=integ_undo_d, retry=_DEFAULT_RETRY, timeout=_DEFAULT_TIMEOUT),
        )

    @workflow.run
    async def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        return await self._run_saga(input_data)


@workflow.defn(sandboxed=False)
class StuckMultiStepWorkflow(SagaWorkflow):
    """step_a → step_flaky (MANUAL_INTERVENTION) → step_always_fail (MANUAL_INTERVENTION) → step_c.

    step_flaky succeeds on retry (2nd attempt).
    step_always_fail always fails and must be skipped.
    """

    def steps(self) -> StepSequence:
        return (
            Step(fn=integ_step_a, undo=integ_undo_a, retry=_DEFAULT_RETRY, timeout=_DEFAULT_TIMEOUT),
            Step(
                fn=integ_step_flaky,
                undo=integ_undo_flaky,
                retry=_DEFAULT_RETRY,
                timeout=_DEFAULT_TIMEOUT,
                on_failure=FailurePolicy.MANUAL_INTERVENTION,
            ),
            Step(
                fn=integ_step_always_fail,
                undo=integ_undo_always_fail,
                retry=_DEFAULT_RETRY,
                timeout=_DEFAULT_TIMEOUT,
                on_failure=FailurePolicy.MANUAL_INTERVENTION,
            ),
            Step(fn=integ_step_c, undo=integ_undo_c, retry=_DEFAULT_RETRY, timeout=_DEFAULT_TIMEOUT),
        )

    @workflow.run
    async def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        return await self._run_saga(input_data)


@workflow.defn(sandboxed=False)
class BlockingInterventionWorkflow(SagaWorkflow):
    """step_a → step_always_fail (MANUAL_INTERVENTION).

    Stays stuck at WAITING_INTERVENTION until signaled or cancelled.
    Used in the ops drain test.
    """

    def steps(self) -> StepSequence:
        return (
            Step(fn=integ_step_a, undo=integ_undo_a, retry=_DEFAULT_RETRY, timeout=_DEFAULT_TIMEOUT),
            Step(
                fn=integ_step_always_fail,
                undo=integ_undo_always_fail,
                retry=_DEFAULT_RETRY,
                timeout=_DEFAULT_TIMEOUT,
                on_failure=FailurePolicy.MANUAL_INTERVENTION,
            ),
        )

    @workflow.run
    async def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        return await self._run_saga(input_data)


_TEST_WORKFLOW_CLASSES: list[type[SagaWorkflow]] = [
    HappyPathIntegrationWorkflow,
    MixedSequentialParallelWorkflow,
    StuckMultiStepWorkflow,
    BlockingInterventionWorkflow,
]


# ── fixtures ──────────────────────────────────────────────────────────


@pytest.fixture()
def register_test_workflows(mocker: MockerFixture) -> None:
    """Patch _register_workflows to call the original production registration
    first, then register integration-test workflows on top."""
    workflows_module = "simcore_service_dynamic_scheduler.services.workflows"

    def _register_with_test_workflows(registry: WorkflowRegistry) -> None:
        _register_production_workflows(registry)
        for wf_cls in _TEST_WORKFLOW_CLASSES:
            registry.register(name=wf_cls.__name__, workflow_cls=wf_cls)

    mocker.patch(
        f"{workflows_module}._lifespan._register_workflows",
        new=_register_with_test_workflows,
    )


@pytest.fixture()
def app_environment(
    docker_stack: dict,
    monkeypatch: pytest.MonkeyPatch,
    docker_compose_service_dynamic_scheduler_env_vars: EnvVarsDict,
) -> EnvVarsDict:
    host = get_localhost_ip()
    return setenvs_from_dict(
        monkeypatch,
        {
            **docker_compose_service_dynamic_scheduler_env_vars,
            "DYNAMIC_SCHEDULER_TRACING": "null",
            "TEMPORALIO_HOST": host,
            "TEMPORALIO_PORT": str(get_service_published_port("temporal", 7233)),
            "POSTGRES_HOST": host,
            "POSTGRES_PORT": str(get_service_published_port("postgres", 5432)),
            "RABBIT_HOST": host,
            "RABBIT_PORT": str(get_service_published_port("rabbit", 5672)),
            "REDIS_HOST": host,
            "REDIS_PORT": str(get_service_published_port("redis", 6379)),
        },
    )


_MAX_TIME_FOR_APP_TO_STARTUP: Final[float] = 120
_MAX_TIME_FOR_APP_TO_SHUTDOWN: Final[float] = 30


@pytest.fixture()
async def app(
    app_environment: EnvVarsDict,
    register_test_workflows: None,
    is_pdb_enabled: bool,
) -> AsyncIterator[FastAPI]:
    nicegui.app.user_middleware.clear()
    nicegui.app.middleware_stack = None
    test_app = create_app()
    async with LifespanManager(
        test_app,
        startup_timeout=None if is_pdb_enabled else _MAX_TIME_FOR_APP_TO_STARTUP,
        shutdown_timeout=None if is_pdb_enabled else _MAX_TIME_FOR_APP_TO_SHUTDOWN,
    ):
        yield test_app


@pytest.fixture()
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://dynamic-scheduler.testserver.io",
        headers={"Content-Type": "application/json"},
    ) as httpx_client:
        yield httpx_client


@pytest.fixture()
def engine(app: FastAPI) -> WorkflowEngine:
    return get_workflow_engine(app)
