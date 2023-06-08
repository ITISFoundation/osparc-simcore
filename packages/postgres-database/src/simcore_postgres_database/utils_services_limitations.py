import datetime
from dataclasses import dataclass

import aiopg.sa
from sqlalchemy import literal_column

from .models.services_limitations import services_limitations


@dataclass(frozen=True, slots=True, kw_only=True)
class ServiceLimitation:
    gid: int
    cluster_id: int | None
    ram: int | None
    cpu: float | None
    vram: int | None
    gpu: float | None
    created: datetime.datetime
    modified: datetime.datetime


class ServicesLimitationsRepo:
    async def create(
        self,
        conn: aiopg.sa.SAConnection,
        *,
        gid: int,
        cluster_id: int | None,
        ram: int | None,
        cpu: float | None,
        vram: int | None,
        gpu: int | None
    ) -> ServiceLimitation:
        async with conn.begin():
            insert_stmt = (
                services_limitations.insert()
                .values(
                    gid=gid, cluster_id=cluster_id, ram=ram, cpu=cpu, vram=vram, gpu=gpu
                )
                .returning(literal_column("*"))
            )
            result = await conn.execute(insert_stmt)
            created_entry = await result.first()
            assert created_entry  # nosec
        return ServiceLimitation(**dict(created_entry.items()))
