import logging
from typing import Any, Dict

from models_library.service_settings_labels import SimcoreServiceSettingsLabel
from servicelib.json_serialization import json_dumps

from ....core.settings import AppSettings, DynamicSidecarSettings
from ....models.schemas.constants import DYNAMIC_SIDECAR_SCHEDULER_DATA_LABEL
from ....models.schemas.dynamic_services import SchedulerData, ServiceType
from .._namepsace import get_compose_namespace
from ..volumes_resolver import DynamicSidecarVolumesPathsResolver
from .settings import inject_settings_to_create_service_params

log = logging.getLogger(__name__)


def extract_service_port_from_compose_start_spec(
    create_service_params: Dict[str, Any]
) -> int:
    return create_service_params["labels"]["service_port"]


def _get_environment_variables(
    compose_namespace: str, scheduler_data: SchedulerData, app_settings: AppSettings
) -> Dict[str, str]:
    registry_settings = app_settings.DIRECTOR_V2_DOCKER_REGISTRY
    rabbit_settings = app_settings.DIRECTOR_V2_RABBITMQ
    r_clone_settings = (
        app_settings.DYNAMIC_SERVICES.DYNAMIC_SIDECAR.DYNAMIC_SIDECAR_R_CLONE_SETTINGS
    )

    state_exclude = []
    if scheduler_data.paths_mapping.state_exclude is not None:
        state_exclude = scheduler_data.paths_mapping.state_exclude

    return {
        "SIMCORE_HOST_NAME": scheduler_data.service_name,
        "DYNAMIC_SIDECAR_COMPOSE_NAMESPACE": compose_namespace,
        "DY_SIDECAR_PATH_INPUTS": f"{scheduler_data.paths_mapping.inputs_path}",
        "DY_SIDECAR_PATH_OUTPUTS": f"{scheduler_data.paths_mapping.outputs_path}",
        "DY_SIDECAR_STATE_PATHS": json_dumps(
            [f"{x}" for x in scheduler_data.paths_mapping.state_paths]
        ),
        "DY_SIDECAR_STATE_EXCLUDE": json_dumps([f"{x}" for x in state_exclude]),
        "DY_SIDECAR_USER_ID": f"{scheduler_data.user_id}",
        "DY_SIDECAR_PROJECT_ID": f"{scheduler_data.project_id}",
        "DY_SIDECAR_NODE_ID": f"{scheduler_data.node_uuid}",
        "POSTGRES_HOST": f"{app_settings.POSTGRES.POSTGRES_HOST}",
        "POSTGRES_ENDPOINT": f"{app_settings.POSTGRES.POSTGRES_HOST}:{app_settings.POSTGRES.POSTGRES_PORT}",
        "POSTGRES_PASSWORD": f"{app_settings.POSTGRES.POSTGRES_PASSWORD.get_secret_value()}",
        "POSTGRES_PORT": f"{app_settings.POSTGRES.POSTGRES_PORT}",
        "POSTGRES_USER": f"{app_settings.POSTGRES.POSTGRES_USER}",
        "POSTGRES_DB": f"{app_settings.POSTGRES.POSTGRES_DB}",
        "STORAGE_ENDPOINT": app_settings.DIRECTOR_V2_STORAGE.storage_endpoint,
        "REGISTRY_AUTH": f"{registry_settings.REGISTRY_AUTH}",
        "REGISTRY_PATH": f"{registry_settings.REGISTRY_PATH}",
        "REGISTRY_URL": f"{registry_settings.REGISTRY_URL}",
        "REGISTRY_USER": f"{registry_settings.REGISTRY_USER}",
        "REGISTRY_PW": f"{registry_settings.REGISTRY_PW.get_secret_value()}",
        "REGISTRY_SSL": f"{registry_settings.REGISTRY_SSL}",
        "RABBIT_HOST": f"{rabbit_settings.RABBIT_HOST}",
        "RABBIT_PORT": f"{rabbit_settings.RABBIT_PORT}",
        "RABBIT_USER": f"{rabbit_settings.RABBIT_USER}",
        "RABBIT_PASSWORD": f"{rabbit_settings.RABBIT_PASSWORD.get_secret_value()}",
        "RABBIT_CHANNELS": json_dumps(rabbit_settings.RABBIT_CHANNELS),
        "S3_ENDPOINT": r_clone_settings.R_CLONE_S3.S3_ENDPOINT,
        "S3_ACCESS_KEY": r_clone_settings.R_CLONE_S3.S3_ACCESS_KEY,
        "S3_SECRET_KEY": r_clone_settings.R_CLONE_S3.S3_SECRET_KEY,
        "S3_BUCKET_NAME": r_clone_settings.R_CLONE_S3.S3_BUCKET_NAME,
        "S3_SECURE": f"{r_clone_settings.R_CLONE_S3.S3_SECURE}",
        "R_CLONE_PROVIDER": r_clone_settings.R_CLONE_PROVIDER,
    }


def get_dynamic_sidecar_spec(
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
    compose_namespace = get_compose_namespace(scheduler_data.node_uuid)

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
    #   `volume_name/path/to/state/01:/target_folder/path_to_state_01`
    #
    # Two separate volumes are required to achieve the following on the spawned
    # dynamic-sidecar containers:
    #   `volume_name_path_to_inputs:/target_folder/path/to/inputs`
    #   `volume_name_path_to_outputs:/target_folder/path/to/outputs`
    #   `volume_name_path_to_state_01:/target_folder/path/to/state/01`
    for path_to_mount in [
        scheduler_data.paths_mapping.inputs_path,
        scheduler_data.paths_mapping.outputs_path,
    ]:
        mounts.append(
            DynamicSidecarVolumesPathsResolver.mount_entry(
                swarm_stack_name=dynamic_sidecar_settings.SWARM_STACK_NAME,
                compose_namespace=compose_namespace,
                path=path_to_mount,
                node_uuid=scheduler_data.node_uuid,
            )
        )
    # state paths now get mounted via different driver and are synced to s3 automatically
    for path_to_mount in scheduler_data.paths_mapping.state_paths:
        # for now only enable this with dev features enabled
        if app_settings.DIRECTOR_V2_DEV_FEATURES_ENABLED:
            mounts.append(
                DynamicSidecarVolumesPathsResolver.mount_r_clone(
                    swarm_stack_name=dynamic_sidecar_settings.SWARM_STACK_NAME,
                    compose_namespace=compose_namespace,
                    path=path_to_mount,
                    project_id=scheduler_data.project_id,
                    node_uuid=scheduler_data.node_uuid,
                    r_clone_settings=dynamic_sidecar_settings.DYNAMIC_SIDECAR_R_CLONE_SETTINGS,
                )
            )
        else:
            mounts.append(
                DynamicSidecarVolumesPathsResolver.mount_entry(
                    swarm_stack_name=dynamic_sidecar_settings.SWARM_STACK_NAME,
                    compose_namespace=compose_namespace,
                    path=path_to_mount,
                    node_uuid=scheduler_data.node_uuid,
                )
            )

    endpoint_spec = {}

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
    # expose this service on an empty port
    if dynamic_sidecar_settings.DYNAMIC_SIDECAR_EXPOSE_PORT:
        endpoint_spec["Ports"] = [
            {
                "Protocol": "tcp",
                "TargetPort": dynamic_sidecar_settings.DYNAMIC_SIDECAR_PORT,
            }
        ]

    create_service_params = {
        "endpoint_spec": endpoint_spec,
        "labels": {
            # TODO: let's use a pydantic model with descriptions
            "io.simcore.zone": scheduler_data.simcore_traefik_zone,
            "traefik.docker.network": scheduler_data.dynamic_sidecar_network_name,  # also used for scheduling
            "traefik.enable": "true",
            f"traefik.http.routers.{scheduler_data.service_name}.entrypoints": "http",
            f"traefik.http.routers.{scheduler_data.service_name}.priority": "10",
            f"traefik.http.routers.{scheduler_data.service_name}.rule": "PathPrefix(`/`)",
            f"traefik.http.services.{scheduler_data.service_name}.loadbalancer.server.port": f"{dynamic_sidecar_settings.DYNAMIC_SIDECAR_PORT}",
            "type": ServiceType.MAIN.value,  # required to be listed as an interactive service and be properly cleaned up
            "user_id": f"{scheduler_data.user_id}",
            "port": f"{dynamic_sidecar_settings.DYNAMIC_SIDECAR_PORT}",
            "study_id": f"{scheduler_data.project_id}",
            # the following are used for scheduling
            "uuid": f"{scheduler_data.node_uuid}",  # also needed for removal when project is closed
            "swarm_stack_name": dynamic_sidecar_settings.SWARM_STACK_NAME,  # required for listing services with uuid
            DYNAMIC_SIDECAR_SCHEDULER_DATA_LABEL: scheduler_data.as_label_data(),
            "service_image": dynamic_sidecar_settings.DYNAMIC_SIDECAR_IMAGE,
        },
        "name": scheduler_data.service_name,
        "networks": [swarm_network_id, dynamic_sidecar_network_id],
        "task_template": {
            "ContainerSpec": {
                "Env": _get_environment_variables(
                    compose_namespace, scheduler_data, app_settings
                ),
                "Hosts": [],
                "Image": dynamic_sidecar_settings.DYNAMIC_SIDECAR_IMAGE,
                "Init": True,
                "Labels": {},
                "Mounts": mounts,
            },
            "Placement": {
                "Constraints": app_settings.DIRECTOR_V2_SERVICES_CUSTOM_CONSTRAINTS
            },
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
