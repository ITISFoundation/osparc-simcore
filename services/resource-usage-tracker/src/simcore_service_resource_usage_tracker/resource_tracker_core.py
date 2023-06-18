import asyncio
import json
import logging
from typing import Any

import arrow
from fastapi import FastAPI
from prometheus_api_client import PrometheusConnect
from simcore_service_resource_usage_tracker.modules.prometheus import (
    get_prometheus_api_client,
)

from .models.resource_tracker_container import ContainerResourceUsage
from .modules.db.repositories.resource_tracker import ResourceTrackerRepository

_logger = logging.getLogger(__name__)


async def _prometheus_client_custom_query(
    prometheus_client: PrometheusConnect, promql_cpu_query: str
) -> list[dict]:
    _logger.info("Querying prometheus with: %s", promql_cpu_query)
    data: list[dict] = await asyncio.get_event_loop().run_in_executor(
        None, prometheus_client.custom_query(promql_cpu_query)
    )
    return data


async def _scrape_and_upload_container_resource_usage(
    prometheus_client: PrometheusConnect,
    resource_tracker_repo: ResourceTrackerRepository,
    image_regex: str = "registry.osparc.io/simcore/services/dynamic/jupyter-smash:.*",
) -> None:
    # Query CPU seconds
    promql_cpu_query = f"sum without (cpu) (container_cpu_usage_seconds_total{{image=~'{image_regex}'}})[30m:1m]"
    containers_cpu_seconds_usage: list = await _prometheus_client_custom_query(
        prometheus_client, promql_cpu_query
    )
    _logger.info(
        "Recieved %s containers from Prometheus", len(containers_cpu_seconds_usage)
    )

    for item in containers_cpu_seconds_usage:
        # Prepare metric
        metric: dict[str, Any] = item["metric"]
        container_label_simcore_service_settings: list[dict[str, Any]] = json.loads(
            metric["container_label_simcore_service_settings"]
        )
        cpu_reservation: int | None = None
        ram_reservation: int | None = None
        for setting in container_label_simcore_service_settings:
            if setting.get("type") == "Resources":
                cpu_reservation = int(setting["value"]["Reservations"]["NanoCPUs"])
                ram_reservation = int(setting["value"]["Reservations"]["MemoryBytes"])
                break

        # Prepare values
        values: list[list] = item["values"]
        first_value: list = values[0]
        last_value: list = values[-1]
        assert len(first_value) == 2  # nosec
        assert len(last_value) == 2  # nosec

        container_resource_usage = ContainerResourceUsage(
            container_id=metric["id"],
            image=metric["image"],
            user_id=metric["container_label_user_id"],
            product_name=metric["container_label_product_name"],
            cpu_reservation=cpu_reservation,
            ram_reservation=ram_reservation,
            container_cpu_usage_seconds_total=last_value[1],
            created_timestamp=arrow.get(first_value[0]),
            last_prometheus_scraped_timestamp=arrow.get(last_value[0]),
        )

        await resource_tracker_repo.upsert_resource_tracker_container_data_(
            container_resource_usage
        )


async def collect_container_resource_usage(
    prometheus_client: PrometheusConnect, db_engine: Any
) -> None:
    await _scrape_and_upload_container_resource_usage(prometheus_client, db_engine)


async def collect_container_resource_usage_task(app: FastAPI) -> None:
    await collect_container_resource_usage(
        get_prometheus_api_client(app),
        ResourceTrackerRepository(db_engine=app.state.engine),
    )
