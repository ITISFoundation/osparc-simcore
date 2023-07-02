from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import Depends
from models_library.products import ProductName
from models_library.resource_tracker import ContainerListAPI, ContainerStatus
from models_library.services import ServiceKey, ServiceVersion
from models_library.users import UserID
from pydantic import PositiveInt

from ..api.dependencies import get_repository
from ..models.pagination import LimitOffsetParamsWithDefault
from ..models.resource_tracker_container import ContainerListDB
from ..modules.db.repositories.resource_tracker import ResourceTrackerRepository

_MAGIC_NUMBER = 3.5  # We will need to store pricing in the DB


async def list_containers(
    user_id: UserID,
    product_name: ProductName,
    page_params: Annotated[LimitOffsetParamsWithDefault, Depends()],
    resource_tacker_repo: ResourceTrackerRepository = Depends(
        get_repository(ResourceTrackerRepository)
    ),
) -> tuple[list[ContainerListAPI], PositiveInt]:
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
        ContainerListDB
    ] = await resource_tacker_repo.list_containers_by_user_and_product(
        user_id, product_name, page_params.offset, page_params.limit
    )

    # Prepare response
    tracked_containers_api_model: list[ContainerListAPI] = []
    for container in tracked_containers_db_model:
        _duration_mins = (
            container.prometheus_last_scraped - container.prometheus_created
        ).total_seconds() / 60

        _service_key, _service_version = container.image.split(":")

        # Split the string at "/"
        split_parts = _service_key.split("/")
        # Find the index of "/simcore/"
        simcore_index = split_parts.index("simcore")
        # Extract the desired part
        _service_key = "/".join(split_parts[simcore_index:])

        _processors = (
            container.service_settings_reservation_nano_cpus / 1e9
            if container.service_settings_reservation_nano_cpus
            else 0.0
        )

        if (
            overall_last_scraped_timestamp - timedelta(minutes=16)
            > container.prometheus_last_scraped
        ):
            _status = ContainerStatus.FINISHED
        else:
            _status = ContainerStatus.RUNNING

        _core_hours = round((_duration_mins / 60) * _processors * _MAGIC_NUMBER, 2)

        tracked_containers_api_model.append(
            ContainerListAPI(
                project_uuid=container.project_uuid,
                project_name=container.project_name,
                node_uuid=container.node_uuid,
                node_label=container.node_label,
                service_key=ServiceKey(_service_key),
                service_version=ServiceVersion(_service_version),
                start_time=container.prometheus_created,
                duration=round(_duration_mins, 2),
                processors=round(_processors, 2),
                core_hours=_core_hours,
                status=_status,
            )
        )

    return (tracked_containers_api_model, total_containers)
