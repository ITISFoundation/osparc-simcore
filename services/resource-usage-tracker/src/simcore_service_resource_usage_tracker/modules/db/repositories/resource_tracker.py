import logging
from typing import cast

import sqlalchemy as sa
from models_library.products import ProductName
from models_library.resource_tracker import ServiceRunId, ServiceRunStatus
from models_library.users import UserID
from models_library.wallets import WalletID
from pydantic import PositiveInt, parse_obj_as
from simcore_postgres_database.models.resource_tracker_service_runs import (
    resource_tracker_service_runs,
)

from ....models.resource_tracker_service_run import (
    CreateServiceRun,
    ServiceRunDB,
    UpdateServiceRunLastHeartbeat,
    UpdateServiceRunStoppedAt,
)
from ._base import BaseRepository

# from sqlalchemy.dialects.postgresql import insert as pg_insert


_logger = logging.getLogger(__name__)


class ResourceTrackerRepository(BaseRepository):
    #############
    # Service Run
    #############

    def service_runs_select_stmt(self):
        return sa.select(
            resource_tracker_service_runs.c.service_run_id,
            resource_tracker_service_runs.c.wallet_id,
            resource_tracker_service_runs.c.wallet_name,
            resource_tracker_service_runs.c.pricing_plan_id,
            resource_tracker_service_runs.c.pricing_detail_id,
            resource_tracker_service_runs.c.user_id,
            resource_tracker_service_runs.c.user_email,
            resource_tracker_service_runs.c.project_id,
            resource_tracker_service_runs.c.project_name,
            resource_tracker_service_runs.c.node_id,
            resource_tracker_service_runs.c.node_name,
            resource_tracker_service_runs.c.service_key,
            resource_tracker_service_runs.c.service_version,
            resource_tracker_service_runs.c.service_type,
            resource_tracker_service_runs.c.service_resources,
            resource_tracker_service_runs.c.started_at,
            resource_tracker_service_runs.c.stopped_at,
            resource_tracker_service_runs.c.service_run_status,
        )

    async def create_service_run(self, data: CreateServiceRun):  # -> ServiceRunId:
        async with self.db_engine.begin() as conn:
            insert_stmt = (
                resource_tracker_service_runs.insert()
                .values(
                    product_name=data.product_name,
                    service_run_id=data.service_run_id,
                    wallet_id=data.wallet_id,
                    wallet_name=data.wallet_name,
                    pricing_plan_id=data.pricing_plan_id,
                    pricing_detail_id=data.pricing_detail_id,
                    simcore_user_agent=data.simcore_user_agent,
                    user_id=data.user_id,
                    user_email=data.user_email,
                    project_id=f"{data.project_id}",
                    project_name=data.product_name,
                    node_id=f"{data.node_id}",
                    node_name=data.node_name,
                    service_key=data.service_key,
                    service_version=data.service_version,
                    service_type=data.service_type,
                    service_resources=data.service_resources,
                    service_additional_metadata=data.service_additional_metadata,
                    started_at=data.started_at,
                    stopped_at=None,
                    service_run_status=ServiceRunStatus.RUNNING,
                    modified=sa.func.now(),
                    last_heartbeat_at=data.last_heartbeat_at,
                )
                .returning(resource_tracker_service_runs.c.service_run_id)
            )
            result = await conn.execute(insert_stmt)
        row = result.first()
        if row is None:
            return None
        return parse_obj_as(ServiceRunId, row[0])

    async def update_service_run_last_heartbeat(
        self, data: UpdateServiceRunLastHeartbeat
    ) -> ServiceRunId | None:
        async with self.db_engine.begin() as conn:
            update_stmt = (
                resource_tracker_service_runs.update()
                .values(
                    modified=sa.func.now(), last_heartbeat_at=data.last_heartbeat_at
                )
                .where(
                    (
                        resource_tracker_service_runs.c.service_run_id
                        == data.service_run_id
                    )
                    & (
                        resource_tracker_service_runs.c.service_run_status
                        == ServiceRunStatus.RUNNING
                    )
                    & (
                        resource_tracker_service_runs.c.last_heartbeat_at
                        <= data.last_heartbeat_at
                    )
                )
                .returning(resource_tracker_service_runs.c.service_run_id)
            )
            result = await conn.execute(update_stmt)
        row = result.first()
        if row is None:
            return None
        return parse_obj_as(ServiceRunId, row[0])

    async def update_service_run_stopped_at(
        self, data: UpdateServiceRunStoppedAt
    ) -> ServiceRunId | None:
        async with self.db_engine.begin() as conn:
            update_stmt = (
                resource_tracker_service_runs.update()
                .values(
                    modified=sa.func.now(),
                    stopped_at=data.stopped_at,
                    service_run_status=data.service_run_status,
                )
                .where(
                    (
                        resource_tracker_service_runs.c.service_run_id
                        == data.service_run_id
                    )
                    & (
                        resource_tracker_service_runs.c.service_run_status  ## .is_
                        == ServiceRunStatus.RUNNING
                    )
                )
                .returning(resource_tracker_service_runs.c.service_run_id)
            )
            result = await conn.execute(update_stmt)
        row = result.first()
        if row is None:
            return None
        return parse_obj_as(ServiceRunId, row[0])

    async def get_service_run(self, service_run_id: ServiceRunId) -> list[ServiceRunDB]:
        async with self.db_engine.begin() as conn:
            query = self.service_runs_select_stmt().where(
                resource_tracker_service_runs.c.service_run_id == service_run_id
            )

            result = await conn.execute(query)

        services_runs = [
            ServiceRunDB(**row) for row in result.fetchall()  # type: ignore[arg-type]
        ]
        return services_runs

    async def list_service_runs_by_user_and_product(
        self, user_id: UserID, product_name: ProductName, offset: int, limit: int
    ) -> list[ServiceRunDB]:
        async with self.db_engine.begin() as conn:
            query = (
                self.service_runs_select_stmt()
                .where(
                    (resource_tracker_service_runs.c.user_id == user_id)
                    & (resource_tracker_service_runs.c.product_name == product_name)
                )
                .order_by(resource_tracker_service_runs.c.started_at.desc())
                .offset(offset)
                .limit(limit)
            )
            result = await conn.execute(query)

        services_runs = [
            ServiceRunDB(**row) for row in result.fetchall()  # type: ignore[arg-type]
        ]
        return services_runs

    async def total_service_runs_by_user_and_product(
        self, user_id: UserID, product_name: ProductName
    ) -> PositiveInt:
        async with self.db_engine.begin() as conn:
            query = (
                sa.select(sa.func.count())
                .select_from(resource_tracker_service_runs)
                .where(
                    (resource_tracker_service_runs.c.user_id == user_id)
                    & (resource_tracker_service_runs.c.product_name == product_name)
                )
            )
            result = await conn.execute(query)
        row = result.first()
        return cast(PositiveInt, row[0]) if row else 0

    async def list_service_runs_by_user_and_product_and_wallet(
        self,
        user_id: UserID,
        product_name: ProductName,
        wallet_id: WalletID,
        offset: int,
        limit: int,
    ) -> list[ServiceRunDB]:
        async with self.db_engine.begin() as conn:
            query = (
                self.service_runs_select_stmt()
                .where(
                    (resource_tracker_service_runs.c.user_id == user_id)
                    & (resource_tracker_service_runs.c.product_name == product_name)
                    & (resource_tracker_service_runs.c.wallet_id == wallet_id)
                )
                .order_by(resource_tracker_service_runs.c.started_at.desc())
                .offset(offset)
                .limit(limit)
            )
            result = await conn.execute(query)

        services_runs = [
            ServiceRunDB(**row) for row in result.fetchall()  # type: ignore[arg-type]
        ]
        return services_runs

    async def total_service_runs_by_user_and_product_and_wallet(
        self, user_id: UserID, product_name: ProductName, wallet_id: WalletID
    ) -> PositiveInt:
        async with self.db_engine.begin() as conn:
            query = (
                sa.select(sa.func.count())
                .select_from(resource_tracker_service_runs)
                .where(
                    (resource_tracker_service_runs.c.user_id == user_id)
                    & (resource_tracker_service_runs.c.product_name == product_name)
                    & (resource_tracker_service_runs.c.wallet_id == wallet_id)
                )
            )
            result = await conn.execute(query)

        row = result.first()
        return cast(PositiveInt, row[0]) if row else 0

    async def list_service_runs_by_product_and_wallet(
        self,
        product_name: ProductName,
        wallet_id: WalletID,
        offset: int,
        limit: int,
    ) -> list[ServiceRunDB]:
        async with self.db_engine.begin() as conn:
            query = (
                self.service_runs_select_stmt()
                .where(
                    (resource_tracker_service_runs.c.wallet_id == wallet_id)
                    & (resource_tracker_service_runs.c.product_name == product_name)
                )
                .order_by(resource_tracker_service_runs.c.started_at.desc())
                .offset(offset)
                .limit(limit)
            )
            result = await conn.execute(query)

        services_runs = [
            ServiceRunDB(**row) for row in result.fetchall()  # type: ignore[arg-type]
        ]
        return services_runs

    async def total_service_runs_by_product_and_wallet(
        self, product_name: ProductName, wallet_id: WalletID
    ) -> PositiveInt:
        async with self.db_engine.begin() as conn:
            query = (
                sa.select(sa.func.count())
                .select_from(resource_tracker_service_runs)
                .where(
                    (resource_tracker_service_runs.c.wallet_id == wallet_id)
                    & (resource_tracker_service_runs.c.product_name == product_name)
                )
            )
            result = await conn.execute(query)

        row = result.first()
        return cast(PositiveInt, row[0]) if row else 0
