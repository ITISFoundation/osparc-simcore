import asyncio
import contextlib
import logging
import os
import socket
from datetime import datetime, timedelta
from typing import Final

from fastapi import FastAPI
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine

from . import registry
from .models import DbDirection, StepClaim
from .repository import ServicesSchedulerRepository

_logger = logging.getLogger(__name__)

_DEFAULT_MAX_CLAIMS: Final[int] = 100
_DEFAULT_HEARTBEAT_INTERVAL: Final[timedelta] = timedelta(seconds=10)
_DEFAULT_HEARTBEAT_EXTEND_BY: Final[timedelta] = timedelta(seconds=30)


class MissingAsyncEngineInAppStateError(TypeError):
    def __init__(self) -> None:
        super().__init__("Missing AsyncEngine in app.state.engine")


class MissingStepHandlerError(RuntimeError):
    def __init__(self, *, step_id: str) -> None:
        super().__init__(f"No step handler registered for step_id={step_id}")


class StepExecutionError(RuntimeError):
    """Expected/handled step execution failure.

    Intent: step handlers should wrap operational failures into this exception
    so the worker can reliably transition the step into `WAITING_MANUAL`.
    """


def _get_async_engine(app: FastAPI) -> AsyncEngine:
    """Return the Postgres async engine from app state.

    Intent: dynamic-scheduler already provisions `app.state.engine` via the
    repository lifespan. The services scheduler reuses that same engine.
    """
    engine = getattr(app.state, "engine", None)
    if not isinstance(engine, AsyncEngine):
        raise MissingAsyncEngineInAppStateError
    return engine


def _get_repo(app: FastAPI) -> ServicesSchedulerRepository:
    """Return the scheduler repository instance.

    Intent: keep the worker self-contained even while the scheduler subsystem
    is still being integrated into the service's lifespan wiring.
    """
    repositories = getattr(app.state, "repositories", None)
    if isinstance(repositories, dict):
        existing = repositories.get(ServicesSchedulerRepository.__name__)
        if isinstance(existing, ServicesSchedulerRepository):
            return existing

        repo = ServicesSchedulerRepository(_get_async_engine(app))
        repositories[ServicesSchedulerRepository.__name__] = repo
        return repo

    repo = getattr(app.state, "services_scheduler_repo", None)
    if isinstance(repo, ServicesSchedulerRepository):
        return repo

    repo = ServicesSchedulerRepository(_get_async_engine(app))
    app.state.services_scheduler_repo = repo
    return repo


def _get_worker_id(app: FastAPI) -> str:
    """Return a stable worker identifier for leases.

    Intent: store a best-effort, process-stable id on app state so all claims
    from this worker share the same `worker_id`.
    """
    existing = getattr(app.state, "services_scheduler_worker_id", None)
    if isinstance(existing, str) and existing:
        return existing

    hostname = socket.gethostname()
    pid = os.getpid()
    worker_id = f"{hostname}:{pid}"
    app.state.services_scheduler_worker_id = worker_id
    return worker_id


async def try_drain(app: FastAPI, *, max_claims: int = _DEFAULT_MAX_CLAIMS) -> None:
    """Drain available runnable steps by repeatedly claiming and executing.

    Intent: this is the core "do work now" entrypoint used by either:
    - a periodic poll loop, and/or
    - a wakeup consumer (RabbitMQ) that triggers immediate draining.

    `max_claims` provides backpressure so a single call does not monopolize the
    event loop.
    """
    repo = _get_repo(app)
    worker_id = _get_worker_id(app)

    # Best-effort recovery: ensure we don't deadlock progress on expired RUNNING leases.
    await repo.recover_expired_running_steps()

    claims_executed = 0
    while claims_executed < max_claims:
        claim = await repo.claim_one_step(worker_id=worker_id)
        if claim is None:
            return

        claims_executed += 1
        await _execute_claim(app, claim=claim)


async def recover_expired_leases(app: FastAPI, *, limit: int = 100) -> int:
    """Public helper to reap expired RUNNING leases.

    Intended to be called from a periodic background task.
    """
    repo = _get_repo(app)
    return await repo.recover_expired_running_steps(limit=limit)


async def _execute_claim(app: FastAPI, *, claim: StepClaim) -> None:
    """Execute a claimed step and persist the outcome.

    Intent: map a claimed (run_id, step_id, direction) to the registered step
    handler and ensure the DB is updated even if the worker is being cancelled.
    """
    repo = _get_repo(app)
    handler = None

    try:
        handler = registry.get_step(claim.step_id)
    except KeyError:
        error = MissingStepHandlerError(step_id=claim.step_id)
        if claim.direction == DbDirection.DO:
            await asyncio.shield(repo.mark_step_abandoned(claim=claim, error=f"{error}"))
            await asyncio.shield(repo.mark_run_cancel_requested(run_id=claim.run_id))
        else:
            # for UNDO case
            await asyncio.shield(repo.mark_step_waiting_manual(claim=claim, error=f"{error}"))
        _logger.warning("%s", error)
        return

    heartbeat_task = asyncio.create_task(_heartbeat_loop(app, claim=claim, interval=_DEFAULT_HEARTBEAT_INTERVAL))
    try:
        if claim.direction == DbDirection.DO:
            await handler.do(app=app, claim=claim)
        else:
            await handler.undo(app=app, claim=claim)

        await asyncio.shield(repo.mark_step_succeeded(claim=claim))
        await asyncio.shield(repo.try_finalize_run(run_id=claim.run_id))
    except StepExecutionError as err:
        if claim.direction == DbDirection.DO:
            await asyncio.shield(repo.mark_step_abandoned(claim=claim, error=f"{err}"))
            await asyncio.shield(repo.mark_run_cancel_requested(run_id=claim.run_id))
        else:
            # for UNDO case
            await asyncio.shield(repo.mark_step_waiting_manual(claim=claim, error=f"{err}"))
    finally:
        heartbeat_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await heartbeat_task


async def _heartbeat_loop(
    app: FastAPI,
    *,
    claim: StepClaim,
    interval: timedelta,
) -> None:
    """Periodically extend a lease while a step is running."""
    repo = _get_repo(app)

    while True:
        await asyncio.sleep(interval.total_seconds())
        try:
            now = datetime.now(tz=claim.lease_until.tzinfo)
            if claim.lease_until <= now:
                continue

            await asyncio.shield(repo.heartbeat_step(claim=claim, extend_by=_DEFAULT_HEARTBEAT_EXTEND_BY))
        except (SQLAlchemyError, TimeoutError):
            _logger.exception(
                "Failed to heartbeat run_id=%s step_id=%s direction=%s",
                claim.run_id,
                claim.step_id,
                claim.direction,
            )


# TODO: create a function that runs in the background which recovers  # noqa: FIX002
async def worker_runner(app: FastAPI) -> None:
    await recover_expired_leases(app)
    await try_drain(app)
