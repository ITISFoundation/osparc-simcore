import datetime
from dataclasses import asdict, dataclass

import aiopg.sa
import psycopg2
import psycopg2.errors
from sqlalchemy import literal_column

from .models.services_limitations import services_limitations


#
# Errors
#
class BaseServicesLimitationsError(Exception):
    ...


class ServiceLimitationsOperationNotAllowed(BaseServicesLimitationsError):
    ...


@dataclass(frozen=True, slots=True, kw_only=True)
class ServiceLimitationsCreate:
    gid: int
    cluster_id: int | None
    ram: int | None
    cpu: float | None
    vram: int | None
    gpu: float | None


@dataclass(frozen=True, slots=True, kw_only=True)
class ServiceLimitations(ServiceLimitationsCreate):
    created: datetime.datetime
    modified: datetime.datetime


class ServicesLimitationsRepo:
    async def create(
        self, conn: aiopg.sa.SAConnection, *, new_limits: ServiceLimitationsCreate
    ) -> ServiceLimitations:
        try:
            async with conn.begin():
                insert_stmt = (
                    services_limitations.insert()
                    .values(**asdict(new_limits))
                    .returning(literal_column("*"))
                )
                result = await conn.execute(insert_stmt)
                created_entry = await result.first()
                assert created_entry  # nosec
            return ServiceLimitations(**dict(created_entry.items()))
        except psycopg2.errors.UniqueViolation as exc:
            raise ServiceLimitationsOperationNotAllowed(
                f"Service limitations for that combination of ({new_limits.gid=}, {new_limits.cluster_id=})"
            ) from exc

    async def update(
        self, conn: aiopg.sa.SAConnection, *, gid: int, cluster_id: int | None, **values
    ) -> ServiceLimitations:
        async with conn.begin():
            update_stmt = (
                services_limitations.update()
                .values(**values)
                .where(
                    (services_limitations.c.gid == gid)
                    & (services_limitations.c.cluster_id == cluster_id)
                )
                .returning(literal_column("*"))
            )
            result = await conn.execute(update_stmt)
            updated_entry = await result.first()
            assert updated_entry  # nosec
        return ServiceLimitations(**dict(updated_entry.items()))
