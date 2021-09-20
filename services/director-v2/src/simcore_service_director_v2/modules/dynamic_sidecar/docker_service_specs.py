import json
import logging
from pathlib import Path
from typing import Any, Dict

from models_library.service_settings_labels import SimcoreServiceSettingsLabel

from ...core.settings import (
    AppSettings,
    DynamicSidecarSettings,
    DynamicSidecarTraefikSettings,
)
from ...models.schemas.constants import DYNAMIC_SIDECAR_SERVICE_PREFIX
from ...models.schemas.dynamic_services import SchedulerData, ServiceType
from ...utils.registry import get_dynamic_sidecar_env_vars
from .docker_service_specs_settings import inject_settings_to_create_service_params
from .volumes_resolver import DynamicSidecarVolumesPathsResolver

log = logging.getLogger(__name__)


def extract_service_port_from_compose_start_spec(
    create_service_params: Dict[str, Any]
) -> int:
    return create_service_params["labels"]["service_port"]


async def get_dynamic_proxy_spec(
    scheduler_data: SchedulerData,
    dynamic_sidecar_settings: DynamicSidecarSettings,
    dynamic_sidecar_network_id: str,
    swarm_network_id: str,
    swarm_network_name: str,
    dynamic_sidecar_node_id: str,
) -> Dict[str, Any]:
    """
    The Traefik proxy is the entrypoint which forwards
    all the network requests to dynamic service.
    The proxy is used to create network isolation
    from the rest of the platform.
    """

    mounts = [
        # docker socket needed to use the docker api
        {
            "Source": "/var/run/docker.sock",
            "Target": "/var/run/docker.sock",
            "Type": "bind",
            "ReadOnly": True,
        }
    ]
    traefik_settings: DynamicSidecarTraefikSettings = (
        dynamic_sidecar_settings.DYNAMIC_SIDECAR_TRAEFIK_SETTINGS
    )

    return {
        "labels": {
            # TODO: let's use a pydantic model with descriptions
            "io.simcore.zone": f"{dynamic_sidecar_settings.TRAEFIK_SIMCORE_ZONE}",
            "swarm_stack_name": dynamic_sidecar_settings.SWARM_STACK_NAME,
            "traefik.docker.network": swarm_network_name,
            "traefik.enable": "true",
            f"traefik.http.middlewares.{scheduler_data.proxy_service_name}-security-headers.headers.customresponseheaders.Content-Security-Policy": f"frame-ancestors {scheduler_data.request_dns}",
            f"traefik.http.middlewares.{scheduler_data.proxy_service_name}-security-headers.headers.accesscontrolallowmethods": "GET,OPTIONS,PUT,POST,DELETE,PATCH,HEAD",
            f"traefik.http.middlewares.{scheduler_data.proxy_service_name}-security-headers.headers.accessControlAllowOriginList": f"{scheduler_data.request_scheme}://{scheduler_data.request_dns}",
            f"traefik.http.middlewares.{scheduler_data.proxy_service_name}-security-headers.headers.accesscontrolmaxage": "100",
            f"traefik.http.middlewares.{scheduler_data.proxy_service_name}-security-headers.headers.addvaryheader": "true",
            f"traefik.http.services.{scheduler_data.proxy_service_name}.loadbalancer.server.port": "80",
            f"traefik.http.routers.{scheduler_data.proxy_service_name}.entrypoints": "http",
            f"traefik.http.routers.{scheduler_data.proxy_service_name}.priority": "10",
            f"traefik.http.routers.{scheduler_data.proxy_service_name}.rule": f"hostregexp(`{scheduler_data.node_uuid}.services.{{host:.+}}`)",
            f"traefik.http.routers.{scheduler_data.proxy_service_name}.middlewares": f"{dynamic_sidecar_settings.SWARM_STACK_NAME}_gzip@docker, {scheduler_data.proxy_service_name}-security-headers",
            "type": ServiceType.DEPENDENCY.value,
            "dynamic_type": "dynamic-sidecar",  # tagged as dynamic service
            "study_id": f"{scheduler_data.project_id}",
            "user_id": f"{scheduler_data.user_id}",
            "uuid": f"{scheduler_data.node_uuid}",  # needed for removal when project is closed
        },
        "name": scheduler_data.proxy_service_name,
        "networks": [swarm_network_id, dynamic_sidecar_network_id],
        "task_template": {
            "ContainerSpec": {
                "Env": {},
                "Hosts": [],
                "Image": f"traefik:{traefik_settings.DYNAMIC_SIDECAR_TRAEFIK_VERSION}",
                "Init": True,
                "Labels": {},
                "Command": [
                    "traefik",
                    f"--log.level={traefik_settings.DYNAMIC_SIDECAR_TRAEFIK_LOGLEVEL}",
                    f"--accesslog={traefik_settings.access_log_as_string}",
                    "--entryPoints.http.address=:80",
                    "--entryPoints.http.forwardedHeaders.insecure",
                    "--providers.docker.endpoint=unix:///var/run/docker.sock",
                    f"--providers.docker.network={scheduler_data.dynamic_sidecar_network_name}",
                    "--providers.docker.exposedByDefault=false",
                    f"--providers.docker.constraints=Label(`io.simcore.zone`, `{scheduler_data.simcore_traefik_zone}`)",
                    # TODO: add authentication once a middleware is in place
                    # something like https://doc.traefik.io/traefik/middlewares/forwardauth/
                ],
                "Mounts": mounts,
            },
            "Placement": {
                "Constraints": [
                    "node.platform.os == linux",
                    f"node.id == {dynamic_sidecar_node_id}",
                ]
            },
            "Resources": {  # starts from 100 MB and maxes at 250 MB with 10% max CPU usage
                "Limits": {"MemoryBytes": 262144000, "NanoCPUs": 100000000},
                "Reservations": {"MemoryBytes": 104857600, "NanoCPUs": 100000000},
            },
            "RestartPolicy": {
                "Condition": "on-failure",
                "Delay": 5000000,
                "MaxAttempts": 2,
            },
        },
    }


def _get_dy_sidecar_env_vars(
    scheduler_data: SchedulerData, app_settings: AppSettings
) -> Dict[str, str]:
    return {
        "DY_SIDECAR_PATH_INPUTS": f"{scheduler_data.paths_mapping.inputs_path}",
        "DY_SIDECAR_PATH_OUTPUTS": f"{scheduler_data.paths_mapping.outputs_path}",
        "DY_SIDECAR_STATE_PATHS": json.dumps(
            [str(x) for x in scheduler_data.paths_mapping.state_paths]
        ),
        "DY_SIDECAR_USER_ID": f"{scheduler_data.user_id}",
        "DY_SIDECAR_PROJECT_ID": f"{scheduler_data.project_id}",
        "DY_SIDECAR_NODE_ID": f"{scheduler_data.node_uuid}",
        "POSTGRES_HOST": f"{app_settings.POSTGRES.POSTGRES_HOST}",
        "POSTGRES_ENDPOINT": f"{app_settings.POSTGRES.POSTGRES_HOST}:{app_settings.POSTGRES.POSTGRES_PORT}",
        "POSTGRES_PASSWORD": f"{app_settings.POSTGRES.POSTGRES_PASSWORD.get_secret_value()}",
        "POSTGRES_PORT": f"{app_settings.POSTGRES.POSTGRES_PORT}",
        "POSTGRES_USER": f"{app_settings.POSTGRES.POSTGRES_USER}",
        "POSTGRES_DB": f"{app_settings.POSTGRES.POSTGRES_DB}",
        "STORAGE_ENDPOINT": app_settings.STORAGE_ENDPOINT,
    }


async def get_dynamic_sidecar_spec(
    scheduler_data: SchedulerData,
    dynamic_sidecar_settings: DynamicSidecarSettings,
    dynamic_sidecar_network_id: str,
    swarm_network_id: str,
    settings: SimcoreServiceSettingsLabel,
    app_settings: AppSettings,
) -> Dict[str, Any]:
    """
    The dynamic-sidecar is responsible for managing the lifecycle
    of the dynamic service. The director-v2 directly coordinates with
    the dynamic-sidecar for this purpose.
    """
    # To avoid collisions for started docker resources a unique identifier is computed:
    # - avoids container level collisions on same node
    # - avoids volume level collisions on same node
    compose_namespace = f"{DYNAMIC_SIDECAR_SERVICE_PREFIX}_{scheduler_data.node_uuid}"

    mounts = [
        # docker socket needed to use the docker api
        {
            "Source": "/var/run/docker.sock",
            "Target": "/var/run/docker.sock",
            "Type": "bind",
        }
    ]

    # Docker does not allow mounting of subfolders from volumes as the following:
    #   `volume_name/inputs:/target_folder/inputs`
    #   `volume_name/outputs:/target_folder/inputs`
    #   `volume_name/path/to/sate/01:/target_folder/path_to_sate_01`
    #
    # Two separate volumes are required to achieve the following on the spawned
    # dynamic-sidecar containers:
    #   `volume_name_inputs:/target_folder/inputs`
    #   `volume_name_outputs:/target_folder/outputs`
    #   `volume_name_path_to_sate_01:/target_folder/path_to_sate_01`
    for path_to_mount in [
        Path("/inputs"),
        Path("/outputs"),
    ] + scheduler_data.paths_mapping.state_paths:
        mounts.append(
            DynamicSidecarVolumesPathsResolver.mount_entry(
                compose_namespace=compose_namespace,
                state_path=path_to_mount,
                node_uuid=f"{scheduler_data.node_uuid}",
            )
        )

    endpint_spec = {}

    if dynamic_sidecar_settings.DYNAMIC_SIDECAR_MOUNT_PATH_DEV is not None:
        dynamic_sidecar_path = dynamic_sidecar_settings.DYNAMIC_SIDECAR_MOUNT_PATH_DEV
        if dynamic_sidecar_path is None:
            log.warning(
                (
                    "Could not mount the sources for the dynamic-sidecar, please "
                    "provide env var named DEV_SIMCORE_DYNAMIC_SIDECAR_PATH"
                )
            )
        else:
            mounts.append(
                {
                    "Source": str(dynamic_sidecar_path),
                    "Target": "/devel/services/dynamic-sidecar",
                    "Type": "bind",
                }
            )
            packages_path = (
                dynamic_sidecar_settings.DYNAMIC_SIDECAR_MOUNT_PATH_DEV
                / ".."
                / ".."
                / "packages"
            )
            mounts.append(
                {
                    "Source": str(packages_path),
                    "Target": "/devel/packages",
                    "Type": "bind",
                }
            )
            storage_client_sdk_path = (
                dynamic_sidecar_settings.DYNAMIC_SIDECAR_MOUNT_PATH_DEV
                / ".."
                / "storage"
                / "client-sdk"
                / "python"
            )
            mounts.append(
                {
                    "Source": str(storage_client_sdk_path),
                    "Target": "/devel/services/storage/client-sdk/python",
                    "Type": "bind",
                }
            )
    # expose this service on an empty port
    if dynamic_sidecar_settings.DYNAMIC_SIDECAR_EXPOSE_PORT:
        endpint_spec["Ports"] = [
            {
                "Protocol": "tcp",
                "TargetPort": dynamic_sidecar_settings.DYNAMIC_SIDECAR_PORT,
            }
        ]

    create_service_params = {
        "endpoint_spec": endpint_spec,
        "labels": {
            # TODO: let's use a pydantic model with descriptions
            "io.simcore.zone": scheduler_data.simcore_traefik_zone,
            "port": f"{dynamic_sidecar_settings.DYNAMIC_SIDECAR_PORT}",
            "study_id": f"{scheduler_data.project_id}",
            "traefik.docker.network": scheduler_data.dynamic_sidecar_network_name,  # also used for scheduling
            "traefik.enable": "true",
            f"traefik.http.routers.{scheduler_data.service_name}.entrypoints": "http",
            f"traefik.http.routers.{scheduler_data.service_name}.priority": "10",
            f"traefik.http.routers.{scheduler_data.service_name}.rule": "PathPrefix(`/`)",
            f"traefik.http.services.{scheduler_data.service_name}.loadbalancer.server.port": f"{dynamic_sidecar_settings.DYNAMIC_SIDECAR_PORT}",
            "type": ServiceType.MAIN.value,  # required to be listed as an interactive service and be properly cleaned up
            "user_id": f"{scheduler_data.user_id}",
            # the following are used for scheduling
            "uuid": f"{scheduler_data.node_uuid}",  # also needed for removal when project is closed
            "swarm_stack_name": dynamic_sidecar_settings.SWARM_STACK_NAME,
            "service_key": scheduler_data.key,
            "service_tag": scheduler_data.version,
            "paths_mapping": scheduler_data.paths_mapping.json(),
            "compose_spec": json.dumps(scheduler_data.compose_spec),
            "container_http_entry": scheduler_data.container_http_entry,
        },
        "name": scheduler_data.service_name,
        "networks": [swarm_network_id, dynamic_sidecar_network_id],
        "task_template": {
            "ContainerSpec": {
                "Env": {
                    "SIMCORE_HOST_NAME": scheduler_data.service_name,
                    "DYNAMIC_SIDECAR_COMPOSE_NAMESPACE": compose_namespace,
                    **get_dynamic_sidecar_env_vars(dynamic_sidecar_settings.REGISTRY),
                    **_get_dy_sidecar_env_vars(scheduler_data, app_settings),
                },
                "Hosts": [],
                "Image": dynamic_sidecar_settings.DYNAMIC_SIDECAR_IMAGE,
                "Init": True,
                "Labels": {},
                "Mounts": mounts,
            },
            "Placement": {"Constraints": []},
            "RestartPolicy": {
                "Condition": "on-failure",
                "Delay": 5000000,
                "MaxAttempts": 2,
            },
            # this will get overwritten
            "Resources": {
                "Limits": {"NanoCPUs": 2 * pow(10, 9), "MemoryBytes": 1 * pow(1024, 3)},
                "Reservations": {
                    "NanoCPUs": 1 * pow(10, 8),
                    "MemoryBytes": 500 * pow(1024, 2),
                },
            },
        },
    }

    inject_settings_to_create_service_params(
        labels_service_settings=settings,
        create_service_params=create_service_params,
    )

    return create_service_params
