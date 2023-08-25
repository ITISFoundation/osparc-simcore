import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import arrow
from aiocache import cached
from fastapi import FastAPI
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.services import ServiceKey, ServiceVersion
from prometheus_api_client import PrometheusConnect
from pydantic import BaseModel, ByteSize
from simcore_postgres_database.models.resource_tracker_containers import (
    ContainerClassification,
)
from simcore_service_resource_usage_tracker.modules.prometheus import (
    get_prometheus_api_client,
)

from ...models.resource_tracker_container import ContainerScrapedResourceUsage
from ...modules.db.repositories.resource_tracker_container import (
    ResourceTrackerContainerRepository,
)
from ...modules.db.repositories.user_and_project import UserAndProjectRepository

_logger = logging.getLogger(__name__)

_TTL = 300  # 5 minutes

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


def _build_cache_key_user_id(fct, *args):
    return f"{fct.__name__}_{args[1]}"


@cached(ttl=_TTL, key_builder=_build_cache_key_user_id)
async def _get_user_email(
    osparc_repo: UserAndProjectRepository, user_id: int
) -> str | None:
    user_email: str | None = await osparc_repo.get_user_email(user_id)
    return user_email


async def _get_project_and_node_names(
    osparc_repo: UserAndProjectRepository, project_uuid: ProjectID, node_uuid: NodeID
) -> tuple[str | None, str | None]:
    if output := await osparc_repo.get_project_name_and_workbench(project_uuid):
        project_name, project_workbench = output
        return (project_name, project_workbench[f"{node_uuid}"].get("label"))
    return (None, None)


async def _scrape_container_resource_usage(
    prometheus_client: PrometheusConnect,
    osparc_repo: UserAndProjectRepository,
    image_regex: str,
    scrape_timestamp: datetime = datetime.now(tz=timezone.utc),
) -> list[ContainerScrapedResourceUsage]:
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

    data: list[ContainerScrapedResourceUsage] = []
    for item in containers_cpu_seconds_usage:
        # Prepare values
        values: list[list] = item["values"]
        first_value: list = values[0]
        last_value: list = values[-1]
        assert len(first_value) == 2  # nosec
        assert len(last_value) == 2  # nosec

        # Prepare metric
        metric: dict[str, Any] = item["metric"]

        memory_limit = int(metric["container_label_io_simcore_runtime_memory_limit"])
        cpu_limit = float(metric["container_label_io_simcore_runtime_cpu_limit"])

        product_name = metric["container_label_io_simcore_runtime_product_name"]
        user_id = int(metric["container_label_io_simcore_runtime_user_id"])
        project_uuid = ProjectID(
            metric["container_label_io_simcore_runtime_project_id"]
        )
        node_uuid = NodeID(metric["container_label_io_simcore_runtime_node_id"])
        user_email, project_info = await asyncio.gather(
            *[
                _get_user_email(osparc_repo, user_id),
                _get_project_and_node_names(osparc_repo, project_uuid, node_uuid),
            ]
        )
        project_name, node_label = project_info

        service_key, service_version = metric["image"].split(":")
        # Split the string at "/"
        split_parts = service_key.split("/")
        # Find the index of "/simcore/"
        simcore_index = split_parts.index("simcore")
        # Extract the desired part
        service_key = "/".join(split_parts[simcore_index:])

        container_resource_usage = ContainerScrapedResourceUsage(
            container_id=metric["id"],
            user_id=user_id,
            product_name=product_name,
            project_uuid=project_uuid,
            memory_limit=ByteSize(memory_limit),
            cpu_limit=cpu_limit,
            service_settings_reservation_additional_info={},
            container_cpu_usage_seconds_total=last_value[1],
            prometheus_created=arrow.get(first_value[0]),
            prometheus_last_scraped=arrow.get(last_value[0]),
            node_uuid=node_uuid,
            instance=metric.get("instance", None),
            project_name=project_name,
            node_label=node_label,
            user_email=user_email,
            service_key=ServiceKey(service_key),
            service_version=ServiceVersion(service_version),
            classification=ContainerClassification.USER_SERVICE,
        )

        data.append(container_resource_usage)

    return data


def _prepare_prom_query_parameters(
    machine_fqdn: str,
    prometheus_last_scraped_timestamp: datetime | None,
    current_timestamp: datetime,
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
    resource_tracker_repo: ResourceTrackerContainerRepository,
    osparc_repo: UserAndProjectRepository,
    machine_fqdn: str,
) -> None:
    prometheus_last_scraped_timestamp: datetime | None = (
        await resource_tracker_repo.get_prometheus_last_scraped_timestamp()
    )
    current_timestamp: datetime = datetime.now(
        tz=timezone.utc
    )  ## NOTE: improve by asking prometheus for current time
    prom_query_params: list[_PromQueryParameters] = _prepare_prom_query_parameters(
        machine_fqdn, prometheus_last_scraped_timestamp, current_timestamp
    )

    for i, parameter in enumerate(prom_query_params):
        _logger.info(
            "Collecting %s/%s with parameter <%s>",
            i + 1,
            len(prom_query_params),
            parameter,
        )
        data: list[
            ContainerScrapedResourceUsage
        ] = await _scrape_container_resource_usage(
            prometheus_client=prometheus_client,
            osparc_repo=osparc_repo,
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
        ResourceTrackerContainerRepository(db_engine=app.state.engine),
        UserAndProjectRepository(
            db_engine=app.state.engine
        ),  # potencionally, will point to different database in the future
        app.state.settings.MACHINE_FQDN,
    )
