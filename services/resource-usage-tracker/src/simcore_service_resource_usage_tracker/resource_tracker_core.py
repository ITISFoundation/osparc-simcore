import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import arrow
from fastapi import FastAPI
from prometheus_api_client import PrometheusConnect
from pydantic import BaseModel
from simcore_service_resource_usage_tracker.modules.prometheus import (
    get_prometheus_api_client,
)

from .models.resource_tracker_container import ContainerResourceUsage
from .modules.db.repositories.resource_tracker import ResourceTrackerRepository

_logger = logging.getLogger(__name__)


_PAST_X_MINUTES = 30  # in promql query the first part: [30m:1m]
_RESOLUTION_MINUTES = 1  # in promql query the second part: [30m:1m]
_PROME_QUERY_PARAMS_TIMEDELTA_MINUTES = (
    25  # should be less than _PAST_X_MINUTES (so there is small overlap)
)


class _PromQueryParameters(BaseModel):
    image_regex: str
    scrape_timestamp: datetime

    class Config:
        validation = False


def _prometheus_sync_client_custom_query(
    prometheus_client: PrometheusConnect,
    promql_cpu_query: str,
    scrape_timestamp: datetime,
) -> list[dict]:
    rfc3339: str = scrape_timestamp.isoformat("T")
    _logger.info("Querying prometheus at <%s> with: <%s>", rfc3339, promql_cpu_query)
    data: list[dict] = prometheus_client.custom_query(
        promql_cpu_query, params={"time": rfc3339}
    )
    return data


async def _scrape_container_resource_usage(
    prometheus_client: PrometheusConnect,
    image_regex: str,
    scrape_timestamp: datetime = datetime.now(tz=timezone.utc),
) -> list[ContainerResourceUsage]:
    # Query CPU seconds
    promql_cpu_query = f"sum without (cpu) (container_cpu_usage_seconds_total{{image=~'{image_regex}'}})[{_PAST_X_MINUTES}m:{_RESOLUTION_MINUTES}m]"
    containers_cpu_seconds_usage: list[
        dict
    ] = await asyncio.get_event_loop().run_in_executor(
        None,
        _prometheus_sync_client_custom_query,
        prometheus_client,
        promql_cpu_query,
        scrape_timestamp,
    )
    _logger.info(
        "Received <%s> containers from Prometheus for image <%s> at <%s>",
        len(containers_cpu_seconds_usage),
        image_regex,
        scrape_timestamp,
    )

    data: list[ContainerResourceUsage] = []
    for item in containers_cpu_seconds_usage:
        # Prepare metric
        metric: dict[str, Any] = item["metric"]
        container_label_simcore_service_settings: list[dict[str, Any]] = json.loads(
            metric["container_label_simcore_service_settings"]
        )
        nano_cpus: int | None = None
        memory_bytes: int | None = None
        for setting in container_label_simcore_service_settings:
            if setting.get("type") == "Resources":
                nano_cpus = (
                    setting.get("value", {})
                    .get("Reservations", {})
                    .get("NanoCPUs", None)
                )
                memory_bytes = (
                    setting.get("value", {})
                    .get("Reservations", {})
                    .get("MemoryBytes", None)
                )
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
            project_uuid=metric["container_label_study_id"],
            service_settings_reservation_nano_cpus=int(nano_cpus)
            if nano_cpus
            else None,
            service_settings_reservation_memory_bytes=int(memory_bytes)
            if memory_bytes
            else None,
            service_settings_reservation_additional_info={},
            container_cpu_usage_seconds_total=last_value[1],
            prometheus_created=arrow.get(first_value[0]),
            prometheus_last_scraped=arrow.get(last_value[0]),
        )

        data.append(container_resource_usage)

    return data


def _prepare_prom_query_parameters(
    machine_fqdn: str,
    prometheus_last_scraped_timestamp: datetime | None,
    current_timestamp: datetime = datetime.now(tz=timezone.utc),
) -> list[_PromQueryParameters]:
    image_regex = f"registry.{machine_fqdn}/simcore/services/dynamic/jupyter-smash:.*"

    # When we start this service for a first time (meaning there is empty database) we start from current timestamp
    scrape_timestamp = (
        prometheus_last_scraped_timestamp
        if prometheus_last_scraped_timestamp
        else current_timestamp
    )

    data = []
    while scrape_timestamp < current_timestamp - timedelta(
        minutes=_PROME_QUERY_PARAMS_TIMEDELTA_MINUTES
    ):
        data.append(
            _PromQueryParameters(
                image_regex=image_regex, scrape_timestamp=scrape_timestamp
            )
        )
        scrape_timestamp = scrape_timestamp + timedelta(
            minutes=_PROME_QUERY_PARAMS_TIMEDELTA_MINUTES
        )
    data.append(
        _PromQueryParameters(
            image_regex=image_regex, scrape_timestamp=current_timestamp
        )
    )
    return data


async def collect_container_resource_usage(
    prometheus_client: PrometheusConnect,
    resource_tracker_repo: ResourceTrackerRepository,
    machine_fqdn: str,
) -> None:
    prometheus_last_scraped_timestamp: datetime | None = (
        await resource_tracker_repo.get_prometheus_last_scraped_timestamp()
    )
    prom_query_params: list[_PromQueryParameters] = _prepare_prom_query_parameters(
        machine_fqdn, prometheus_last_scraped_timestamp
    )

    for i, parameter in enumerate(prom_query_params):
        _logger.info(
            "Collecting %s/%s with parameter <%s>",
            i + 1,
            len(prom_query_params),
            parameter,
        )
        data: list[ContainerResourceUsage] = await _scrape_container_resource_usage(
            prometheus_client=prometheus_client,
            image_regex=parameter.image_regex,
            scrape_timestamp=parameter.scrape_timestamp,
        )

        # Upload to the database
        await asyncio.gather(
            *[
                resource_tracker_repo.upsert_resource_tracker_container_data(
                    container_resource_usage
                )
                for container_resource_usage in data
            ]
        )


async def collect_container_resource_usage_task(app: FastAPI) -> None:
    await collect_container_resource_usage(
        get_prometheus_api_client(app),
        ResourceTrackerRepository(db_engine=app.state.engine),
        app.state.settings.MACHINE_FQDN,
    )
