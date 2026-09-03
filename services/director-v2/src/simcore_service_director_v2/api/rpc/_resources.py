from fastapi import FastAPI
from models_library.products import ProductName
from models_library.service_settings_labels import SimcoreServiceLabels
from models_library.services_resources import ServiceResourcesDict
from models_library.services_types import ServiceKey, ServiceVersion
from models_library.users import UserID
from pydantic import ByteSize
from servicelib.rabbitmq import RPCRouter
from servicelib.rabbitmq.rpc_interfaces.director_v2.errors import (
    InsufficientInstanceResourcesError,
    MissingServiceResourceKeysError,
)

from ...core.settings import AppSettings
from ...modules.catalog import CatalogClient
from ...modules.db.repositories.groups_extra_properties import (
    GroupsExtraPropertiesRepository,
)
from ...modules.dynamic_sidecar.docker_compose_egress_config import (
    count_required_egress_proxies,
)
from ...modules.dynamic_sidecar.docker_service_specs.resources import (
    MissingResourceKeysError,
    NotEnoughInstanceResourcesError,
    scale_service_resources_to_instance_type,
)
from ...utils.db import get_repository

router = RPCRouter()


@router.expose(reraise_if_error_type=(InsufficientInstanceResourcesError, MissingServiceResourceKeysError))
async def scale_service_resources_for_instance_type(
    app: FastAPI,
    *,
    user_id: UserID,
    product_name: ProductName,
    service_key: ServiceKey,
    service_version: ServiceVersion,
    service_resources: ServiceResourcesDict,
    instance_cpus: float,
    instance_ram: ByteSize,
) -> ServiceResourcesDict:
    """Rescales the node's resources to fit the given machine.

    Everything that will run on that machine is accounted for here: the user services,
    the dynamic-sidecar itself and the helper containers it creates. Callers only need
    to persist the result.
    """
    app_settings: AppSettings = app.state.settings
    catalog_client = CatalogClient.instance(app)
    simcore_service_labels: SimcoreServiceLabels = await catalog_client.get_service_labels(service_key, service_version)

    groups_extra_properties = get_repository(app, GroupsExtraPropertiesRepository)
    user_extra_properties = await groups_extra_properties.get_user_extra_properties(
        user_id=user_id, product_name=product_name
    )

    try:
        return scale_service_resources_to_instance_type(
            service_resources,
            dynamic_services_settings=app_settings.DYNAMIC_SERVICES,
            egress_proxy_count=count_required_egress_proxies(simcore_service_labels),
            with_tracing=simcore_service_labels.tracing,
            with_rclone=user_extra_properties.mount_data,
            instance_cpus=instance_cpus,
            instance_ram=instance_ram,
        )
    except NotEnoughInstanceResourcesError as exc:
        raise InsufficientInstanceResourcesError(
            service_key=service_key,
            service_version=service_version,
            instance_cpus=instance_cpus,
            instance_ram=instance_ram,
            cpus=exc.cpus,
            ram=exc.ram,
        ) from exc
    except MissingResourceKeysError as exc:
        raise MissingServiceResourceKeysError(
            service_key=service_key,
            service_version=service_version,
            container_name=exc.container_name,
            missing_key=exc.missing_key,
        ) from exc
