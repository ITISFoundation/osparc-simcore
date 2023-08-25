from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import Depends
from models_library.api_schemas_webserver.resource_usage import (
    ContainerGet,
    ContainerStatus,
)
from models_library.products import ProductName
from models_library.users import UserID
from pydantic import PositiveInt

from ..api.dependencies import get_repository
from ..models.pagination import LimitOffsetParamsWithDefault
from ..models.resource_tracker_container import ContainerGetDB, ContainersPage
from ..modules.db.repositories.resource_tracker_container import (
    ResourceTrackerContainerRepository,
)

_OSPARC_TOKEN_PRICE = 3.5  # We will need to store pricing in the DB


async def list_containers(
    user_id: UserID,
    product_name: ProductName,
    page_params: Annotated[LimitOffsetParamsWithDefault, Depends()],
    resource_tacker_repo: Annotated[
        ResourceTrackerContainerRepository,
        Depends(get_repository(ResourceTrackerContainerRepository)),
    ],
) -> ContainersPage:
    # Prepare helper variables
    overall_last_scraped_timestamp_or_none: datetime | None = (
        await resource_tacker_repo.get_prometheus_last_scraped_timestamp()
    )
    current_timestamp: datetime = datetime.now(
        timezone.utc
    )  # NOTE: improve this by getting the current timestamp from the prometheus
    overall_last_scraped_timestamp: datetime = (
        overall_last_scraped_timestamp_or_none
        if overall_last_scraped_timestamp_or_none
        else current_timestamp
    )

    total_containers: PositiveInt = (
        await resource_tacker_repo.total_containers_by_user_and_product(
            user_id, product_name
        )
    )

    # Get all tracked containers
    tracked_containers_db_model: list[
        ContainerGetDB
    ] = await resource_tacker_repo.list_containers_by_user_and_product(
        user_id, product_name, page_params.offset, page_params.limit
    )

    # Prepare response
    tracked_containers_api_model: list[ContainerGet] = []
    for container in tracked_containers_db_model:
        _duration_mins = (
            container.prometheus_last_scraped - container.prometheus_created
        ).total_seconds() / 60

        _processors = container.cpu_limit

        if (
            overall_last_scraped_timestamp - timedelta(minutes=16)
            > container.prometheus_last_scraped
        ):
            _status = ContainerStatus.FINISHED
        else:
            _status = ContainerStatus.RUNNING

        # NOTE: When we will have "pricing DB table" this will be computed in the SQL
        # so for example total sum could be quickly computed via another endpoint
        _core_hours = round(
            (_duration_mins / 60) * _processors * _OSPARC_TOKEN_PRICE, 2
        )

        tracked_containers_api_model.append(
            ContainerGet.construct(
                project_uuid=container.project_uuid,
                project_name=container.project_name,
                node_uuid=container.node_uuid,
                node_label=container.node_label,
                service_key=container.service_key,
                service_version=container.service_version,
                start_time=container.prometheus_created,
                duration=round(_duration_mins, 2),
                processors=round(_processors, 2),
                core_hours=_core_hours,
                status=_status,
            )
        )

    return ContainersPage(tracked_containers_api_model, total_containers)
