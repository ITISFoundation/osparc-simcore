import logging

from simcore_postgres_database.models.resource_tracker import resource_tracker_container
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert as pg_insert

from ....models.resource_tracker_container import ContainerResourceUsage
from ._base import BaseRepository

_logger = logging.getLogger(__name__)


class ResourceTrackerRepository(BaseRepository):
    async def upsert_resource_tracker_container_data_(
        self, data: ContainerResourceUsage
    ) -> None:
        async with self.db_engine.begin() as conn:
            insert_stmt = pg_insert(resource_tracker_container).values(
                id=data.container_id,
                image=data.image,
                user_id=data.user_id,
                product_name=data.product_name,
                cpu_reservation=data.cpu_reservation,
                ram_reservation=data.ram_reservation,
                container_cpu_usage_seconds_total=data.container_cpu_usage_seconds_total,
                created_timestamp=data.created_timestamp.datetime,
                last_prometheus_scraped_timestamp=data.last_prometheus_scraped_timestamp.datetime,
                last_row_updated_timestamp=func.now(),
            )

            on_update_stmt = insert_stmt.on_conflict_do_update(
                index_elements=[
                    resource_tracker_container.c.id,
                ],
                set_={
                    "container_cpu_usage_seconds_total": func.greatest(
                        resource_tracker_container.c.container_cpu_usage_seconds_total,
                        insert_stmt.excluded.container_cpu_usage_seconds_total,
                    ),
                    "created_timestamp": func.least(
                        resource_tracker_container.c.created_timestamp,
                        insert_stmt.excluded.created_timestamp,
                    ),
                    "last_prometheus_scraped_timestamp": func.greatest(
                        resource_tracker_container.c.last_prometheus_scraped_timestamp,
                        insert_stmt.excluded.last_prometheus_scraped_timestamp,
                    ),
                    "last_row_updated_timestamp": func.now(),
                },
            )

            await conn.execute(on_update_stmt)
