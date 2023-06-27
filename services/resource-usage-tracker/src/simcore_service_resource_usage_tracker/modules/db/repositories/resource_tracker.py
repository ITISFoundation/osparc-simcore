import logging
from datetime import datetime

import sqlalchemy as sa
from simcore_postgres_database.models.resource_tracker import resource_tracker_container
from sqlalchemy.dialects.postgresql import insert as pg_insert

from ....models.resource_tracker_container import ContainerResourceUsage
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
        self, data: ContainerResourceUsage
    ) -> None:
        async with self.db_engine.begin() as conn:
            insert_stmt = pg_insert(resource_tracker_container).values(
                container_id=data.container_id,
                image=data.image,
                user_id=data.user_id,
                project_uuid=str(data.project_uuid),
                product_name=data.product_name,
                service_settings_reservation_nano_cpus=data.service_settings_reservation_nano_cpus,
                service_settings_reservation_memory_bytes=data.service_settings_reservation_memory_bytes,
                service_settings_reservation_additional_info=data.service_settings_reservation_additional_info,
                container_cpu_usage_seconds_total=data.container_cpu_usage_seconds_total,
                prometheus_created=data.prometheus_created.datetime,
                prometheus_last_scraped=data.prometheus_last_scraped.datetime,
                modified=sa.func.now(),
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
