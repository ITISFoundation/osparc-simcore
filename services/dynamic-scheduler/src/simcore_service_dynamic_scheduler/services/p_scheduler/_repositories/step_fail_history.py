from datetime import datetime

import sqlalchemy as sa
from simcore_postgres_database.models.p_scheduler import ps_step_fail_history
from simcore_postgres_database.utils_repos import transaction_context
from sqlalchemy.engine.row import Row

from ...base_repository import BaseRepository
from .._models import StepFailHistory, StepId, StepState


def _row_to_step_fail_history(row: Row) -> StepFailHistory:
    return StepFailHistory(
        step_id=row.step_id,
        attempt=row.attempt,
        state=row.state,
        finished_at=row.finished_at,
        message=row.message,
    )


class StepFailHistoryRepository(BaseRepository):
    async def insert_step_fail_history(
        self, step_id: StepId, attempt: int, state: StepState, finished_at: datetime, message: str
    ) -> None:
        async with transaction_context(self.engine) as conn:
            await conn.execute(
                ps_step_fail_history.insert().values(
                    step_id=step_id,
                    attempt=attempt,
                    state=state,
                    finished_at=finished_at,
                    message=message,
                )
            )

    async def get_step_fail_history(self, step_id: StepId) -> list[StepFailHistory]:
        async with self.engine.connect() as conn:
            result = await conn.execute(sa.select("*").where(ps_step_fail_history.c.step_id == step_id))
        rows = result.fetchall()
        return [_row_to_step_fail_history(row) for row in rows]
