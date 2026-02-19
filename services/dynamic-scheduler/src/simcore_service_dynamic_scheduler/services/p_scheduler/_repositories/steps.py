from typing import Final

import sqlalchemy as sa
from simcore_postgres_database.models.p_scheduler import ps_steps
from simcore_postgres_database.utils_repos import pass_or_acquire_connection, transaction_context
from sqlalchemy.engine.row import Row

from ...base_repository import BaseRepository
from .._abc import BaseStep
from .._models import DagNodeUniqueReference, RunId, Step, StepId, StepState
from .step_fail_history import StepFailHistoryRepository

_DEFAULT_AVAILABLE_ATTEMPTS: Final[int] = 3
_INITIAL_ATTEMPT_NUMBER: Final[int] = 1


def _row_to_step(row: Row) -> Step:
    return Step(
        step_id=row.step_id,
        created_at=row.created_at,
        run_id=row.run_id,
        step_type=row.step_type,
        is_reverting=row.is_reverting,
        timeout=row.timeout,
        available_attempts=row.available_attempts,
        attempt_number=row.attempt_number,
        state=StepState(row.state),
        finished_at=row.finished_at,
        message=row.message,
    )


class StepsRepository(BaseRepository):
    async def create_step(
        self, run_id: RunId, step_type: DagNodeUniqueReference, *, step_class: type[BaseStep], is_reverting: bool
    ) -> Step:
        timeout = step_class.get_revert_timeout() if is_reverting else step_class.get_apply_timeout()
        async with transaction_context(self.engine) as conn:
            result = await conn.execute(
                ps_steps.insert()
                .values(
                    run_id=run_id,
                    step_type=step_type,
                    is_reverting=is_reverting,
                    timeout=timeout,
                    available_attempts=_DEFAULT_AVAILABLE_ATTEMPTS,
                    attempt_number=_INITIAL_ATTEMPT_NUMBER,
                    state=StepState.CREATED,
                )
                .returning(sa.literal_column("*"))
            )
            row = result.one()
        return _row_to_step(row)

    async def set_run_steps_as_cancelled(self, run_id: RunId) -> set[StepId]:
        async with transaction_context(self.engine) as conn:
            result = await conn.execute(
                ps_steps.update()
                .where(
                    (ps_steps.c.run_id == run_id)
                    & (ps_steps.c.state.in_([StepState.CREATED, StepState.READY, StepState.RUNNING]))
                )
                .values(state=StepState.CANCELLED)
                .returning(ps_steps.c.step_id)
            )
        return {row.step_id for row in result.fetchall()}

    async def get_all_run_tracked_steps(self, run_id: RunId) -> set[tuple[DagNodeUniqueReference, bool]]:
        async with pass_or_acquire_connection(self.engine) as conn:
            result = await conn.execute(
                sa.select(ps_steps.c.step_type, ps_steps.c.is_reverting).where(ps_steps.c.run_id == run_id)
            )
            rows = result.fetchall()
        return {(row.step_type, row.is_reverting) for row in rows}

    async def get_all_run_tracked_steps_states(self, run_id: RunId) -> dict[tuple[DagNodeUniqueReference, bool], Step]:
        async with pass_or_acquire_connection(self.engine) as conn:
            result = await conn.execute(sa.select(ps_steps).where(ps_steps.c.run_id == run_id))
            rows = result.fetchall()
        return {(row.step_type, row.is_reverting): _row_to_step(row) for row in rows}

    async def _push_step_to_history(self, step_id: StepId) -> None:
        async with pass_or_acquire_connection(self.engine) as conn:
            result = await conn.execute(
                sa.select(
                    ps_steps.c.attempt_number, ps_steps.c.state, ps_steps.c.finished_at, ps_steps.c.message
                ).where(ps_steps.c.step_id == step_id)
            )
            row = result.one()

        step_fail_history_repo = StepFailHistoryRepository(self.engine)
        await step_fail_history_repo.insert_step_fail_history(
            step_id=step_id,
            attempt=row.attempt_number,
            state=StepState(row.state.value),
            finished_at=row.finished_at,
            message=row.message or "",
        )

    async def retry_failed_step(self, step_id: StepId) -> None:
        await self._push_step_to_history(step_id)

        async with transaction_context(self.engine) as conn:
            await conn.execute(
                ps_steps.update()
                .where(ps_steps.c.step_id == step_id)
                .values(
                    state=StepState.CREATED,
                    attempt_number=ps_steps.c.attempt_number + 1,
                    available_attempts=ps_steps.c.available_attempts - 1,
                    finished_at=None,
                    message=None,
                )
            )

    async def set_step_as_ready(self, step_id: StepId) -> None:
        async with transaction_context(self.engine) as conn:
            await conn.execute(ps_steps.update().where(ps_steps.c.step_id == step_id).values(state=StepState.READY))

    async def get_step_for_workflow_manager(self, step_id: StepId) -> Step | None:
        async with pass_or_acquire_connection(self.engine) as conn:
            result = await conn.execute(sa.select(ps_steps).where(ps_steps.c.step_id == step_id))
            row = result.first()
        if row is None:
            return None
        return _row_to_step(row)

    async def manual_retry_step(self, step_id: StepId) -> None:
        await self._push_step_to_history(step_id)

        async with transaction_context(self.engine) as conn:
            await conn.execute(
                ps_steps.update()
                .where(ps_steps.c.step_id == step_id)
                .values(
                    state=StepState.READY,
                    attempt_number=ps_steps.c.attempt_number + 1,
                    # add an attempt to make sure there is at least one available
                    available_attempts=ps_steps.c.available_attempts + 1,
                    finished_at=None,
                    message=None,
                )
            )

    async def manual_skip_step(self, step_id: StepId) -> None:
        async with transaction_context(self.engine) as conn:
            await conn.execute(ps_steps.update().where(ps_steps.c.step_id == step_id).values(state=StepState.SKIPPED))

    async def get_step_for_worker(self, step_id: StepId | None) -> Step | None:
        async with transaction_context(self.engine) as conn:
            # Select a READY step and lock it; skip rows already locked by other workers
            select_query = (
                sa.select(ps_steps)
                .where(ps_steps.c.state == StepState.READY)
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            if step_id is not None:
                select_query = select_query.where(ps_steps.c.step_id == step_id)

            result = await conn.execute(select_query)
            row = result.first()
            if row is None:
                return None

            # Transition the locked step to RUNNING
            result = await conn.execute(
                ps_steps.update()
                .where(ps_steps.c.step_id == row.step_id)
                .values(state=StepState.RUNNING)
                .returning(sa.literal_column("*"))
            )
            row = result.one()
        return _row_to_step(row)

    async def step_cancelled(self, step_id: StepId) -> None:
        async with transaction_context(self.engine) as conn:
            await conn.execute(ps_steps.update().where(ps_steps.c.step_id == step_id).values(state=StepState.CANCELLED))

    async def step_finished_successfully(self, step_id: StepId) -> None:
        async with transaction_context(self.engine) as conn:
            await conn.execute(
                ps_steps.update()
                .where(ps_steps.c.step_id == step_id)
                .values(state=StepState.SUCCESS, finished_at=sa.func.now())
            )

    async def step_finished_with_failure(self, step_id: StepId, message: str) -> None:
        async with transaction_context(self.engine) as conn:
            await conn.execute(
                ps_steps.update()
                .where(ps_steps.c.step_id == step_id)
                .values(state=StepState.FAILED, finished_at=sa.func.now(), message=message)
            )
