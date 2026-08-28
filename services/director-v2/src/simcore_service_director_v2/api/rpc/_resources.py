from fastapi import FastAPI
from models_library.products import ProductName
from models_library.service_settings_labels import SimcoreServiceLabels
from models_library.services_types import ServiceKey, ServiceVersion
from models_library.users import UserID
from pydantic import ByteSize, TypeAdapter
from servicelib.rabbitmq import RPCRouter
from servicelib.rabbitmq.rpc_interfaces.director_v2.resources import (
    HelperContainersCpuLimit,
    HelperContainersRamLimit,
)
from settings_library.basic_types import TotalCpuCores

from ...core.settings import AppSettings
from ...modules.catalog import CatalogClient
from ...modules.db.repositories.groups_extra_properties import (
    GroupsExtraPropertiesRepository,
)
from ...modules.dynamic_sidecar.docker_compose_egress_config import (
    count_required_egress_proxies,
)
from ...modules.dynamic_sidecar.docker_service_specs.settings import (
    compute_helper_containers_resources,
)
from ...utils.db import get_repository

router = RPCRouter()


@router.expose(reraise_if_error_type=())
async def get_helper_containers_resource_limits(
    app: FastAPI,
    *,
    user_id: UserID,
    product_name: ProductName,
    service_key: ServiceKey,
    service_version: ServiceVersion,
    max_user_service_container_memory: ByteSize,
) -> tuple[HelperContainersCpuLimit, HelperContainersRamLimit]:
    """Extra CPU/RAM to reserve for a user service on top of its own allocation,
    so that callers can subtract it in advance.

    Covers only the helper containers co-located with the user service (see
    `compute_helper_containers_resources` for the breakdown). The dynamic-sidecar
    itself and its proxy are excluded: they are already accounted for by
    `estimate_dynamic_sidecar_resources_from_ec2_instance`. Applied as both
    reservation and limit; 0 means nothing extra is needed.
    """
    app_settings: AppSettings = app.state.settings
    catalog_client = CatalogClient.instance(app)
    simcore_service_labels: SimcoreServiceLabels = await catalog_client.get_service_labels(service_key, service_version)

    groups_extra_properties = get_repository(app, GroupsExtraPropertiesRepository)
    user_extra_properties = await groups_extra_properties.get_user_extra_properties(
        user_id=user_id, product_name=product_name
    )

    cpu, ram = compute_helper_containers_resources(
        dynamic_services_settings=app_settings.DYNAMIC_SERVICES,
        egress_proxy_count=count_required_egress_proxies(simcore_service_labels),
        with_tracing=simcore_service_labels.tracing,
        with_rclone=user_extra_properties.mount_data,
        max_user_service_container_memory=max_user_service_container_memory,
    )
    return TotalCpuCores(cores=cpu), TypeAdapter(ByteSize).validate_python(ram)
