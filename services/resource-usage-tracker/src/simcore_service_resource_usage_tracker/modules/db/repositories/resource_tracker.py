import logging
from datetime import datetime
from typing import cast

import sqlalchemy as sa
from models_library.products import ProductName
from models_library.users import UserID
from pydantic import PositiveInt
from simcore_postgres_database.models.resource_tracker_containers import (
    resource_tracker_container,
)
from sqlalchemy.dialects.postgresql import insert as pg_insert

from ....models.resource_tracker_container import (
    ContainerGetDB,
    ContainerScrapedResourceUsage,
)
from ._base import BaseRepository

_logger = logging.getLogger(__name__)


class ResourceTrackerRepository(BaseRepository):
    async def get_prometheus_last_scraped_timestamp(self) -> datetime | None:
        async with self.db_engine.begin() as conn:
            max_last_scraped_timestamp: datetime | None = await conn.scalar(
                sa.select(
                    sa.func.max(resource_tracker_container.c.prometheus_last_scraped)
                )
            )
            return max_last_scraped_timestamp

    async def upsert_resource_tracker_container_data(
        self, data: ContainerScrapedResourceUsage
    ) -> None:
        async with self.db_engine.begin() as conn:
            insert_stmt = pg_insert(resource_tracker_container).values(
                container_id=data.container_id,
                user_id=data.user_id,
                user_email=data.user_email,
                project_uuid=f"{data.project_uuid}",
                project_name=data.project_name,
                product_name=data.product_name,
                cpu_limit=data.cpu_limit,
                memory_limit=data.memory_limit,
                service_settings_reservation_additional_info=data.service_settings_reservation_additional_info,
                container_cpu_usage_seconds_total=data.container_cpu_usage_seconds_total,
                prometheus_created=data.prometheus_created.datetime,
                prometheus_last_scraped=data.prometheus_last_scraped.datetime,
                modified=sa.func.now(),
                node_uuid=f"{data.node_uuid}",
                node_label=data.node_label,
                instance=data.instance,
                service_key=data.service_key,
                service_version=data.service_version,
                classification=data.classification,
            )

            on_update_stmt = insert_stmt.on_conflict_do_update(
                index_elements=[
                    resource_tracker_container.c.container_id,
                ],
                set_={
                    "container_cpu_usage_seconds_total": sa.func.greatest(
                        resource_tracker_container.c.container_cpu_usage_seconds_total,
                        insert_stmt.excluded.container_cpu_usage_seconds_total,
                    ),
                    "prometheus_created": sa.func.least(
                        resource_tracker_container.c.prometheus_created,
                        insert_stmt.excluded.prometheus_created,
                    ),
                    "prometheus_last_scraped": sa.func.greatest(
                        resource_tracker_container.c.prometheus_last_scraped,
                        insert_stmt.excluded.prometheus_last_scraped,
                    ),
                    "modified": sa.func.now(),
                },
            )

            await conn.execute(on_update_stmt)

    async def list_containers_by_user_and_product(
        self, user_id: UserID, product_name: ProductName, offset: int, limit: int
    ) -> list[ContainerGetDB]:
        async with self.db_engine.begin() as conn:
            query = (
                sa.select(
                    resource_tracker_container.c.cpu_limit,
                    resource_tracker_container.c.memory_limit,
                    resource_tracker_container.c.prometheus_created,
                    resource_tracker_container.c.prometheus_last_scraped,
                    resource_tracker_container.c.project_uuid,
                    resource_tracker_container.c.project_name,
                    resource_tracker_container.c.node_uuid,
                    resource_tracker_container.c.node_label,
                    resource_tracker_container.c.service_key,
                    resource_tracker_container.c.service_version,
                )
                .where(
                    (resource_tracker_container.c.user_id == user_id)
                    & (resource_tracker_container.c.product_name == product_name)
                )
                .order_by(resource_tracker_container.c.prometheus_last_scraped.desc())
                .offset(offset)
                .limit(limit)
            )

            result = await conn.execute(query)
            containers_list = [
                ContainerGetDB(**row)  # type: ignore[arg-type]
                for row in result.fetchall()
            ]

            return containers_list

    async def total_containers_by_user_and_product(
        self, user_id: UserID, product_name: ProductName
    ) -> PositiveInt:
        async with self.db_engine.begin() as conn:
            query = (
                sa.select(sa.func.count())
                .select_from(resource_tracker_container)
                .where(
                    (resource_tracker_container.c.user_id == user_id)
                    & (resource_tracker_container.c.product_name == product_name)
                )
            )

            result = await conn.execute(query)
            row = result.first()
            return cast(int, row[0]) if row else 0
