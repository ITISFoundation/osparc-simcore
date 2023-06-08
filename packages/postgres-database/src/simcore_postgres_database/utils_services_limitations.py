import datetime
from dataclasses import asdict, dataclass

import aiopg.sa
import psycopg2
import psycopg2.errors
import sqlalchemy as sa
from sqlalchemy import literal_column

from .models.groups import user_to_groups
from .models.services_limitations import services_limitations


#
# Errors
#
class BaseServicesLimitationsError(Exception):
    ...


class ServiceLimitationsOperationNotAllowed(BaseServicesLimitationsError):
    ...


class ServiceLimitationsOperationNotFound(BaseServicesLimitationsError):
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


@dataclass(frozen=True, slots=True, kw_only=True)
class ServicesLimitationsRepo:
    user_id: int

    @staticmethod
    async def create(
        conn: aiopg.sa.SAConnection, *, new_limits: ServiceLimitationsCreate
    ) -> ServiceLimitations:
        try:
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
                f"Service limitations for ({new_limits.gid=}, {new_limits.cluster_id=}) already exist"
            ) from exc

    @staticmethod
    async def get(
        conn: aiopg.sa.SAConnection, *, gid: int, cluster_id: int | None
    ) -> ServiceLimitations:
        result = await conn.execute(
            sa.select(services_limitations).where(
                (services_limitations.c.gid == gid)
                & (services_limitations.c.cluster_id == cluster_id)
            )
        )
        receive_entry = await result.first()
        if not receive_entry:
            raise ServiceLimitationsOperationNotFound(
                f"Service limitations for ({gid=}, {cluster_id=}) do not exist"
            )
        assert receive_entry  # nosec
        return ServiceLimitations(**dict(receive_entry.items()))

    @staticmethod
    async def update(
        conn: aiopg.sa.SAConnection, *, gid: int, cluster_id: int | None, **values
    ) -> ServiceLimitations:
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
        if not updated_entry:
            raise ServiceLimitationsOperationNotFound(
                f"Service limitations for ({gid=}, {cluster_id=}) do not exist"
            )
        assert updated_entry  # nosec
        return ServiceLimitations(**dict(updated_entry.items()))

    @staticmethod
    async def delete(
        conn: aiopg.sa.SAConnection, *, gid: int, cluster_id: int | None
    ) -> None:
        await conn.execute(
            sa.delete(services_limitations).where(
                (services_limitations.c.gid == gid)
                & (services_limitations.c.cluster_id == cluster_id)
            )
        )

    def _join_user_groups_service_limitations(
        self,
        cluster_id: int | None,
    ):
        j = user_to_groups.join(
            services_limitations,
            (user_to_groups.c.uid == self.user_id)
            & (user_to_groups.c.gid == services_limitations.c.gid)
            & (services_limitations.c.cluster_id == cluster_id),
        )
        return j

    async def list_for_user(
        self, conn: aiopg.sa.SAConnection, *, cluster_id: int | None
    ) -> list[ServiceLimitations]:
        select_stmt = sa.select(services_limitations).select_from(
            self._join_user_groups_service_limitations(cluster_id)
        )
        limits = [
            ServiceLimitations(**dict(row.items()))  # type: ignore
            async for row in conn.execute(select_stmt)
        ]

        return limits
