from datetime import timedelta
from typing import Final

import sqlalchemy as sa
from simcore_postgres_database.models.p_scheduler import ps_step_lease
from simcore_postgres_database.utils_repos import transaction_context
from sqlalchemy.dialects.postgresql import insert as pg_insert

from ...base_repository import BaseRepository
from .._models import StepId, WorkerId

_LEASE_DURATION: Final[timedelta] = timedelta(seconds=30)


class StepsLeaseRepository(BaseRepository):
    async def acquire_or_extend_lease(self, step_id: StepId, worker_id: WorkerId) -> bool:
        """Acquire a new lease or extend an existing one owned by this worker.

        Returns True if the lease was acquired/extended, False if another
        worker holds an unexpired lease for this step.
        """
        now = sa.func.now()
        new_expires_at = now + _LEASE_DURATION

        async with transaction_context(self.engine) as conn:
            insert_stmt = pg_insert(ps_step_lease).values(
                step_id=step_id,
                renew_count=0,
                owner=worker_id,
                acquired_at=now,
                last_heartbeat_at=now,
                expires_at=new_expires_at,
            )
            upsert_stmt = insert_stmt.on_conflict_do_update(
                index_elements=[ps_step_lease.c.step_id],
                set_={
                    "renew_count": ps_step_lease.c.renew_count + 1,
                    "last_heartbeat_at": now,
                    "expires_at": new_expires_at,
                },
                where=((ps_step_lease.c.owner == worker_id) | (ps_step_lease.c.expires_at < now)),
            ).returning(ps_step_lease.c.step_id)
            result = await conn.execute(upsert_stmt)
            row = result.first()

        return row is not None
