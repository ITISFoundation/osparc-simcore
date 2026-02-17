from datetime import datetime

from simcore_postgres_database.models.p_scheduler import ps_step_fail_history
from simcore_postgres_database.utils_repos import transaction_context

from ...base_repository import BaseRepository
from .._models import StepId, StepState


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
