from datetime import timedelta
from typing import Final
from uuid import uuid4

import sqlalchemy as sa
from models_library.projects_nodes_io import NodeID
from simcore_postgres_database.models.dynamic_services_scheduler import (
    dynamic_services_scheduler_nodes,
    dynamic_services_scheduler_runs,
    dynamic_services_scheduler_step_deps,
    dynamic_services_scheduler_step_executions,
)
from simcore_postgres_database.utils_repos import transaction_context
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine
from sqlalchemy.sql.elements import ClauseElement

from .models import (
    DagTemplate,
    DbDesiredState,
    DbDirection,
    DbManualAction,
    DbRunKind,
    DbRunState,
    DbStepState,
    ManualAction,
    RunId,
    StepClaim,
    StepId,
)

_SATISFIED_STATES: Final[tuple[DbStepState, ...]] = (DbStepState.SUCCEEDED, DbStepState.SKIPPED)
_PROBLEM_STATES: Final[tuple[DbStepState, ...]] = (DbStepState.WAITING_MANUAL, DbStepState.ABANDONED)


class ServicesSchedulerRepository:
    """Postgres-backed persistence layer for the dynamic services scheduler.

    Intent: provide small, composable DB operations that the engine/worker can
    combine into higher-level workflows. Methods accept an optional
    `AsyncConnection` so callers can group multiple operations in a single
    transaction.
    """

    def __init__(
        self,
        engine: AsyncEngine,
        *,
        default_lease_duration: timedelta = timedelta(seconds=30),
    ) -> None:
        """Create a repository bound to an `AsyncEngine`.

        `default_lease_duration` is used by `claim_one_step()` when no explicit
        lease duration is provided.
        """
        self._engine = engine
        self._default_lease_duration = default_lease_duration

    @property
    def engine(self) -> AsyncEngine:
        """Expose the underlying SQLAlchemy engine (mainly for transaction helpers)."""
        return self._engine

    def _as_interval(self, duration: timedelta) -> ClauseElement:
        """Convert a Python duration into a Postgres interval expression.

        This is used when extending leases (`now() + interval`).
        """
        seconds = int(duration.total_seconds())
        return sa.text(f"interval '{seconds} seconds'")

    async def lock_node(self, node_id: NodeID, connection: AsyncConnection | None = None) -> None:
        """Ensure a node row exists and acquire a row-level lock on it.

        Intent: serialize operations that mutate node-level state (e.g. creating
        a new run, switching `active_run_id`, bumping desired generation).

        Implementation: upsert-once (insert if missing) then `SELECT .. FOR
        UPDATE` to lock the row until the surrounding transaction commits.
        """
        async with transaction_context(self._engine, connection) as conn:
            await conn.execute(
                pg_insert(dynamic_services_scheduler_nodes)
                .values(
                    node_id=f"{node_id}",
                    desired_state=DbDesiredState.PRESENT,
                    desired_spec={},
                    desired_generation=0,
                )
                .on_conflict_do_nothing(index_elements=[dynamic_services_scheduler_nodes.c.node_id])
            )

            await conn.execute(
                sa.select(dynamic_services_scheduler_nodes.c.node_id)
                .where(dynamic_services_scheduler_nodes.c.node_id == f"{node_id}")
                .with_for_update()
            )

    async def set_node_desired(
        self,
        *,
        node_id: NodeID,
        desired_state: DbDesiredState,
        desired_spec: dict,
        connection: AsyncConnection | None = None,
    ) -> int:
        """Update the node's desired state/spec and bump `desired_generation`.

        Intent: make a desired-state change monotonic and observable. Each call
        increments the generation and returns the new value.
        """
        async with transaction_context(self._engine, connection) as conn:
            result = await conn.execute(
                sa.update(dynamic_services_scheduler_nodes)
                .where(dynamic_services_scheduler_nodes.c.node_id == f"{node_id}")
                .values(
                    desired_state=desired_state,
                    desired_spec=desired_spec,
                    desired_generation=dynamic_services_scheduler_nodes.c.desired_generation + 1,
                )
                .returning(dynamic_services_scheduler_nodes.c.desired_generation)
            )
            return int(result.scalar_one())

    async def create_run(
        self,
        *,
        node_id: NodeID,
        generation: int,
        kind: DbRunKind,
        connection: AsyncConnection | None = None,
    ) -> str:
        """Create a new run row for a node and return its generated `run_id`.

        Intent: represent a concrete attempt to converge a node to the desired
        state (APPLY/TEARDOWN). `generation` links the run to the desired change
        that triggered it.

        Raises:
            ValueError: if `kind` is not a valid `RunKind` enum value.
        """
        run_id = f"{uuid4()}"

        initial_state = DbRunState.TEARING_DOWN if kind is DbRunKind.TEARDOWN else DbRunState.APPLYING

        async with transaction_context(self._engine, connection) as conn:
            await conn.execute(
                sa.insert(dynamic_services_scheduler_runs).values(
                    run_id=run_id,
                    node_id=f"{node_id}",
                    generation=generation,
                    kind=kind,
                    state=initial_state,
                )
            )
        return run_id

    async def mark_run_cancel_requested(self, *, run_id: RunId, connection: AsyncConnection | None = None) -> None:
        """Mark a run as cancel-requested.

        Intent: cooperative cancellation signal. Workers/engine should observe
        this and stop scheduling further APPLY steps (TEARDOWN is typically
        treated as non-cancellable).
        """
        async with transaction_context(self._engine, connection) as conn:
            await conn.execute(
                sa.update(dynamic_services_scheduler_runs)
                .where(dynamic_services_scheduler_runs.c.run_id == run_id)
                .values(
                    state=DbRunState.CANCEL_REQUESTED,
                    cancel_requested_at=sa.func.now(),
                )
            )

    async def set_active_run(
        self,
        *,
        node_id: NodeID,
        run_id: RunId | None,
        connection: AsyncConnection | None = None,
    ) -> None:
        """Set or clear the node's `active_run_id` pointer.

        Intent: provide a single place to learn what run is currently considered
        active for the node (useful for UI/monitoring and for deciding what the
        worker should prioritize).
        """
        async with transaction_context(self._engine, connection) as conn:
            await conn.execute(
                sa.update(dynamic_services_scheduler_nodes)
                .where(dynamic_services_scheduler_nodes.c.node_id == f"{node_id}")
                .values(active_run_id=run_id)
            )

    async def insert_steps(
        self,
        *,
        run_id: RunId,
        direction: DbDirection,
        template: DagTemplate,
        connection: AsyncConnection | None = None,
    ) -> None:
        """Materialize DAG nodes into step-execution rows for a run+direction.

        Intent: convert an in-memory DAG template into durable DB state the
        workers can claim from. This is idempotent via `ON CONFLICT DO NOTHING`.
        """

        rows = [
            {
                "run_id": run_id,
                "step_id": step_id,
                "direction": direction,
                "state": DbStepState.PENDING,
            }
            for step_id in sorted(template.nodes)
        ]
        if not rows:
            return

        async with transaction_context(self._engine, connection) as conn:
            await conn.execute(
                pg_insert(dynamic_services_scheduler_step_executions)
                .values(rows)
                .on_conflict_do_nothing(
                    index_elements=[
                        dynamic_services_scheduler_step_executions.c.run_id,
                        dynamic_services_scheduler_step_executions.c.step_id,
                        dynamic_services_scheduler_step_executions.c.direction,
                    ]
                )
            )

    async def insert_deps(
        self,
        *,
        run_id: RunId,
        direction: DbDirection,
        template: DagTemplate,
        connection: AsyncConnection | None = None,
    ) -> None:
        """Materialize DAG edges into dependency rows for a run+direction.

        Intent: enable DB-side gating of runnable steps: a step can be claimed
        only when all its dependencies are satisfied.
        """

        rows = [
            {
                "run_id": run_id,
                "direction": direction,
                "step_id": step_id,
                "depends_on_step_id": depends_on_step_id,
            }
            for depends_on_step_id, step_id in sorted(template.edges)
        ]
        if not rows:
            return

        async with transaction_context(self._engine, connection) as conn:
            await conn.execute(
                pg_insert(dynamic_services_scheduler_step_deps)
                .values(rows)
                .on_conflict_do_nothing(
                    index_elements=[
                        dynamic_services_scheduler_step_deps.c.run_id,
                        dynamic_services_scheduler_step_deps.c.direction,
                        dynamic_services_scheduler_step_deps.c.step_id,
                        dynamic_services_scheduler_step_deps.c.depends_on_step_id,
                    ]
                )
            )

    async def claim_one_step(
        self,
        *,
        worker_id: str,
        connection: AsyncConnection | None = None,
        # NOTE: callers may override to tune responsiveness vs. DB churn.
        lease_duration: timedelta | None = None,
    ) -> StepClaim | None:
        """Claim one runnable step and return a `StepClaim`, or `None`.

        Intent: implement the core concurrency primitive for workers.

        A step is claimable when:
        - its state is `PENDING`
        - it has no active lease (lease is NULL or expired)
        - all dependencies are satisfied (deps in `SUCCEEDED` or `SKIPPED`)

        Concurrency: uses `FOR UPDATE SKIP LOCKED` on a single candidate row so
        multiple workers can safely compete without double-claiming.
        """
        lease_duration = lease_duration or self._default_lease_duration
        lease_interval = self._as_interval(lease_duration)

        steps = dynamic_services_scheduler_step_executions.alias("steps")
        deps = dynamic_services_scheduler_step_deps.alias("deps")
        prereq_steps = dynamic_services_scheduler_step_executions.alias("prereq")

        satisfied_states = (DbStepState.SUCCEEDED, DbStepState.SKIPPED)
        unmet_dependency_exists = sa.exists(
            sa.select(sa.literal(1))
            .select_from(
                deps.join(
                    prereq_steps,
                    sa.and_(
                        prereq_steps.c.run_id == deps.c.run_id,
                        prereq_steps.c.direction == deps.c.direction,
                        prereq_steps.c.step_id == deps.c.depends_on_step_id,
                    ),
                )
            )
            .where(
                sa.and_(
                    deps.c.run_id == steps.c.run_id,
                    deps.c.direction == steps.c.direction,
                    deps.c.step_id == steps.c.step_id,
                    sa.not_(prereq_steps.c.state.in_(satisfied_states)),
                )
            )
        )

        candidate = (
            sa.select(steps.c.run_id, steps.c.step_id, steps.c.direction)
            .where(
                sa.and_(
                    sa.not_(unmet_dependency_exists),
                    steps.c.state == DbStepState.PENDING,
                    sa.or_(
                        steps.c.lease_until.is_(None),
                        steps.c.lease_until < sa.func.now(),
                    ),
                )
            )
            .order_by(steps.c.modified.asc())
            .with_for_update(skip_locked=True)
            .limit(1)
            .cte("candidate")
        )

        async with transaction_context(self._engine, connection) as conn:
            result = await conn.execute(
                sa.update(dynamic_services_scheduler_step_executions)
                .where(
                    sa.and_(
                        dynamic_services_scheduler_step_executions.c.run_id == candidate.c.run_id,
                        dynamic_services_scheduler_step_executions.c.step_id == candidate.c.step_id,
                        dynamic_services_scheduler_step_executions.c.direction == candidate.c.direction,
                    )
                )
                .values(
                    state=DbStepState.RUNNING,
                    attempt=dynamic_services_scheduler_step_executions.c.attempt + 1,
                    worker_id=worker_id,
                    lease_until=sa.func.now() + lease_interval,
                )
                .returning(
                    dynamic_services_scheduler_step_executions.c.run_id,
                    dynamic_services_scheduler_step_executions.c.step_id,
                    dynamic_services_scheduler_step_executions.c.direction,
                    dynamic_services_scheduler_step_executions.c.attempt,
                    dynamic_services_scheduler_step_executions.c.worker_id,
                    dynamic_services_scheduler_step_executions.c.lease_until,
                )
            )

            row = result.first()
            if not row:
                return None

            return StepClaim(
                run_id=row.run_id,
                step_id=row.step_id,
                direction=DbDirection(row.direction.value),
                attempt=int(row.attempt),
                worker_id=row.worker_id,
                lease_until=row.lease_until,
            )

    async def recover_expired_running_steps(
        self,
        *,
        limit: int = 100,
        connection: AsyncConnection | None = None,
    ) -> int:
        """Recover steps stuck in `RUNNING` whose lease expired.

        Intent: recovery mechanism (Option B) for worker crashes/timeouts.

        Behavior:
        - DO steps: mark step `ABANDONED` (release lease + record error) and mark
          run cancel requested.
        - UNDO steps: mark step `WAITING_MANUAL` (release lease + record error).

        Note: this does not make the step runnable again; it stops progress in a
        durable, inspectable way.
        """
        if limit <= 0:
            return 0

        steps = dynamic_services_scheduler_step_executions.alias("steps")

        async with transaction_context(self._engine, connection) as conn:
            result = await conn.execute(
                sa.select(
                    steps.c.run_id,
                    steps.c.step_id,
                    steps.c.direction,
                )
                .where(
                    sa.and_(
                        steps.c.state == DbStepState.RUNNING,
                        steps.c.lease_until.is_not(None),
                        steps.c.lease_until < sa.func.now(),
                    )
                )
                .order_by(steps.c.lease_until.asc())
                .with_for_update(skip_locked=True)
                .limit(limit)
            )
            rows = result.fetchall()
            if not rows:
                return 0

            reaped = 0
            error_msg = "Lease expired while RUNNING; previous worker likely died"

            for row in rows:
                direction = DbDirection(row.direction)

                if direction is DbDirection.DO:
                    await conn.execute(
                        sa.update(dynamic_services_scheduler_step_executions)
                        .where(
                            sa.and_(
                                dynamic_services_scheduler_step_executions.c.run_id == row.run_id,
                                dynamic_services_scheduler_step_executions.c.step_id == row.step_id,
                                dynamic_services_scheduler_step_executions.c.direction == direction,
                                dynamic_services_scheduler_step_executions.c.state == DbStepState.RUNNING,
                                dynamic_services_scheduler_step_executions.c.lease_until < sa.func.now(),
                            )
                        )
                        .values(
                            state=DbStepState.ABANDONED,
                            last_error=error_msg,
                            manual_required_at=None,
                            lease_until=None,
                            worker_id=None,
                        )
                    )

                    await conn.execute(
                        sa.update(dynamic_services_scheduler_runs)
                        .where(dynamic_services_scheduler_runs.c.run_id == row.run_id)
                        .values(
                            state=DbRunState.CANCEL_REQUESTED,
                            cancel_requested_at=sa.func.now(),
                        )
                    )

                else:
                    # for UNDO case
                    await conn.execute(
                        sa.update(dynamic_services_scheduler_step_executions)
                        .where(
                            sa.and_(
                                dynamic_services_scheduler_step_executions.c.run_id == row.run_id,
                                dynamic_services_scheduler_step_executions.c.step_id == row.step_id,
                                dynamic_services_scheduler_step_executions.c.direction == direction,
                                dynamic_services_scheduler_step_executions.c.state == DbStepState.RUNNING,
                                dynamic_services_scheduler_step_executions.c.lease_until < sa.func.now(),
                            )
                        )
                        .values(
                            state=DbStepState.WAITING_MANUAL,
                            last_error=error_msg,
                            manual_required_at=sa.func.now(),
                            lease_until=None,
                            worker_id=None,
                        )
                    )

                reaped += 1

            return reaped

    async def heartbeat_step(
        self,
        *,
        claim: StepClaim,
        extend_by: timedelta,
        connection: AsyncConnection | None = None,
    ) -> None:
        """Extend a claimed step's lease.

        Intent: allow long-running step handlers to keep ownership while making
        crashed/stalled workers recoverable (lease eventually expires).

        Safety: uses `greatest(lease_until, now())` to avoid accidentally
        shortening the lease due to clock/ordering.
        """
        lease_interval = self._as_interval(extend_by)

        async with transaction_context(self._engine, connection) as conn:
            await conn.execute(
                sa.update(dynamic_services_scheduler_step_executions)
                .where(
                    sa.and_(
                        dynamic_services_scheduler_step_executions.c.run_id == claim.run_id,
                        dynamic_services_scheduler_step_executions.c.step_id == claim.step_id,
                        dynamic_services_scheduler_step_executions.c.direction == claim.direction,
                        dynamic_services_scheduler_step_executions.c.worker_id == claim.worker_id,
                        dynamic_services_scheduler_step_executions.c.state == DbStepState.RUNNING,
                    )
                )
                .values(
                    lease_until=sa.func.greatest(
                        dynamic_services_scheduler_step_executions.c.lease_until,
                        sa.func.now(),
                    )
                    + lease_interval
                )
            )

    async def mark_step_succeeded(self, *, claim: StepClaim, connection: AsyncConnection | None = None) -> None:
        """Mark a claimed step as `SUCCEEDED` and release its lease."""

        async with transaction_context(self._engine, connection) as conn:
            await conn.execute(
                sa.update(dynamic_services_scheduler_step_executions)
                .where(
                    sa.and_(
                        dynamic_services_scheduler_step_executions.c.run_id == claim.run_id,
                        dynamic_services_scheduler_step_executions.c.step_id == claim.step_id,
                        dynamic_services_scheduler_step_executions.c.direction == claim.direction,
                        dynamic_services_scheduler_step_executions.c.worker_id == claim.worker_id,
                    )
                )
                .values(
                    state=DbStepState.SUCCEEDED,
                    lease_until=None,
                )
            )

    async def try_finalize_run(self, *, run_id: RunId, connection: AsyncConnection | None = None) -> bool:
        """Mark a run `SUCCEEDED` and clear the node's `active_run_id` when done.

        Intent: keep `dynamic_services_scheduler_nodes.active_run_id` consistent
        with the run lifecycle.

        A run is considered complete when all step executions for the run's
        relevant direction are in a satisfied state (`SUCCEEDED` or `SKIPPED`).

        Notes:
        - For APPLY runs, the relevant direction is DO.
        - For TEARDOWN runs, the relevant direction is UNDO.
        - This method is idempotent and safe to call after each step finishes.
        """

        async with transaction_context(self._engine, connection) as conn:
            run_row = (
                await conn.execute(
                    sa.select(
                        dynamic_services_scheduler_runs.c.node_id,
                        dynamic_services_scheduler_runs.c.kind,
                        dynamic_services_scheduler_runs.c.state,
                    ).where(dynamic_services_scheduler_runs.c.run_id == run_id)
                )
            ).first()

            if not run_row:
                return False

            kind_value = getattr(run_row.kind, "value", run_row.kind)
            relevant_direction = DbDirection.DO if kind_value == DbRunKind.APPLY.value else DbDirection.UNDO

            remaining_exists = sa.exists(
                sa.select(sa.literal(1))
                .select_from(dynamic_services_scheduler_step_executions)
                .where(
                    sa.and_(
                        dynamic_services_scheduler_step_executions.c.run_id == run_id,
                        dynamic_services_scheduler_step_executions.c.direction == relevant_direction,
                        sa.not_(dynamic_services_scheduler_step_executions.c.state.in_(_SATISFIED_STATES)),
                    )
                )
            )

            still_running = (await conn.execute(sa.select(remaining_exists))).scalar_one()
            if bool(still_running):
                return False

            await conn.execute(
                sa.update(dynamic_services_scheduler_runs)
                .where(dynamic_services_scheduler_runs.c.run_id == run_id)
                .values(state=DbRunState.SUCCEEDED)
            )

            await conn.execute(
                sa.update(dynamic_services_scheduler_nodes)
                .where(
                    sa.and_(
                        dynamic_services_scheduler_nodes.c.node_id == f"{run_row.node_id}",
                        dynamic_services_scheduler_nodes.c.active_run_id == run_id,
                    )
                )
                .values(active_run_id=None)
            )

            return True

    async def run_has_problems(self, *, run_id: RunId, connection: AsyncConnection | None = None) -> bool:
        """Return whether a run has any step in a problem state.

        Intent: allow callers (API/engine/worker) to quickly detect that a run
        needs attention.

        Current definition of "problem": any step execution in either
        `WAITING_MANUAL` (human intervention required) or `ABANDONED`
        (execution failed and will not be retried automatically).
        """

        problem_exists = sa.exists(
            sa.select(sa.literal(1)).where(
                sa.and_(
                    dynamic_services_scheduler_step_executions.c.run_id == run_id,
                    dynamic_services_scheduler_step_executions.c.state.in_(_PROBLEM_STATES),
                )
            )
        )

        async with transaction_context(self._engine, connection) as conn:
            return bool((await conn.execute(sa.select(problem_exists))).scalar_one())

    async def mark_step_waiting_manual(
        self,
        *,
        claim: StepClaim,
        error: str,
        connection: AsyncConnection | None = None,
    ) -> None:
        """Move a step to `WAITING_MANUAL` and record the error.

        Intent: stop automatic progress and require an explicit human decision
        (e.g. retry or skip) while preserving the error context.
        """

        async with transaction_context(self._engine, connection) as conn:
            await conn.execute(
                sa.update(dynamic_services_scheduler_step_executions)
                .where(
                    sa.and_(
                        dynamic_services_scheduler_step_executions.c.run_id == claim.run_id,
                        dynamic_services_scheduler_step_executions.c.step_id == claim.step_id,
                        dynamic_services_scheduler_step_executions.c.direction == claim.direction,
                        dynamic_services_scheduler_step_executions.c.worker_id == claim.worker_id,
                    )
                )
                .values(
                    state=DbStepState.WAITING_MANUAL,
                    last_error=error,
                    manual_required_at=sa.func.now(),
                    lease_until=None,
                    worker_id=None,
                )
            )

    async def mark_step_abandoned(
        self,
        *,
        claim: StepClaim,
        error: str,
        connection: AsyncConnection | None = None,
    ) -> None:
        """Mark a claimed step as `ABANDONED` and release its lease.

        Intent: record a failure without requiring manual intervention on the
        step itself. This is useful for DO failures where the desired behavior
        is to cancel the workflow/run rather than ask a human to retry/skip a
        specific step.
        """

        async with transaction_context(self._engine, connection) as conn:
            await conn.execute(
                sa.update(dynamic_services_scheduler_step_executions)
                .where(
                    sa.and_(
                        dynamic_services_scheduler_step_executions.c.run_id == claim.run_id,
                        dynamic_services_scheduler_step_executions.c.step_id == claim.step_id,
                        dynamic_services_scheduler_step_executions.c.direction == claim.direction,
                        dynamic_services_scheduler_step_executions.c.worker_id == claim.worker_id,
                    )
                )
                .values(
                    state=DbStepState.ABANDONED,
                    last_error=error,
                    manual_required_at=None,
                    lease_until=None,
                    worker_id=None,
                )
            )

    async def apply_manual_action(
        self,
        *,
        run_id: RunId,
        step_id: StepId,
        manual_action: ManualAction,
        connection: AsyncConnection | None = None,
    ) -> None:
        """Apply a manual decision to a `WAITING_MANUAL` step.

        Supported actions:
        - RETRY: returns the step to `PENDING` and clears the last error
        - SKIP: marks the step `SKIPPED` (dependencies treat this as satisfied)
        """

        new_state = DbStepState.PENDING if manual_action.action is DbManualAction.RETRY else DbStepState.SKIPPED

        values: dict[str, object] = {
            "state": new_state,
            "manual_action": manual_action.action,
            "manual_action_at": sa.func.now(),
            "manual_action_by": manual_action.performed_by,
            "manual_action_reason": manual_action.reason,
            "lease_until": None,
            "worker_id": None,
        }
        if new_state is DbStepState.PENDING:
            values["last_error"] = None

        async with transaction_context(self._engine, connection) as conn:
            await conn.execute(
                sa.update(dynamic_services_scheduler_step_executions)
                .where(
                    sa.and_(
                        dynamic_services_scheduler_step_executions.c.run_id == run_id,
                        dynamic_services_scheduler_step_executions.c.step_id == step_id,
                        dynamic_services_scheduler_step_executions.c.state == DbStepState.WAITING_MANUAL,
                    )
                )
                .values(**values)
            )
