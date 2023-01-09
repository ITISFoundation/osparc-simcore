import logging
from copy import deepcopy

from models_library.aiodocker_api import AioDockerServiceSpec
from models_library.basic_types import BootModeEnum
from models_library.service_settings_labels import SimcoreServiceSettingsLabel
from pydantic import parse_obj_as
from servicelib.json_serialization import json_dumps

from ....core.settings import AppSettings, DynamicSidecarSettings
from ....models.schemas.constants import DYNAMIC_SIDECAR_SCHEDULER_DATA_LABEL
from ....models.schemas.dynamic_services import SchedulerData, ServiceType
from .._namespace import get_compose_namespace
from ..volumes import DynamicSidecarVolumesPathsResolver
from ._constants import DOCKER_CONTAINER_SPEC_RESTART_POLICY_DEFAULTS
from .settings import update_service_params_from_settings

log = logging.getLogger(__name__)


def extract_service_port_from_compose_start_spec(
    create_service_params: AioDockerServiceSpec,
) -> int:
    assert create_service_params.Labels  # nosec
    return parse_obj_as(int, create_service_params.Labels["service_port"])


def _get_environment_variables(
    compose_namespace: str, scheduler_data: SchedulerData, app_settings: AppSettings
) -> dict[str, str]:
    registry_settings = app_settings.DIRECTOR_V2_DOCKER_REGISTRY
    rabbit_settings = app_settings.DIRECTOR_V2_RABBITMQ
    r_clone_settings = (
        app_settings.DYNAMIC_SERVICES.DYNAMIC_SIDECAR.DYNAMIC_SIDECAR_R_CLONE_SETTINGS
    )

    state_exclude = set()
    if scheduler_data.paths_mapping.state_exclude is not None:
        state_exclude = scheduler_data.paths_mapping.state_exclude

    return {
        # These environments will be captured by
        # services/dynamic-sidecar/src/simcore_service_dynamic_sidecar/core/settings.py::ApplicationSettings
        #
        "DY_SIDECAR_NODE_ID": f"{scheduler_data.node_uuid}",
        "DY_SIDECAR_PATH_INPUTS": f"{scheduler_data.paths_mapping.inputs_path}",
        "DY_SIDECAR_PATH_OUTPUTS": f"{scheduler_data.paths_mapping.outputs_path}",
        "DY_SIDECAR_PROJECT_ID": f"{scheduler_data.project_id}",
        "DY_SIDECAR_RUN_ID": f"{scheduler_data.run_id}",
        "DY_SIDECAR_STATE_EXCLUDE": json_dumps(f"{x}" for x in state_exclude),
        "DY_SIDECAR_STATE_PATHS": json_dumps(
            f"{x}" for x in scheduler_data.paths_mapping.state_paths
        ),
        "DY_SIDECAR_USER_ID": f"{scheduler_data.user_id}",
        "DYNAMIC_SIDECAR_COMPOSE_NAMESPACE": compose_namespace,
        "DYNAMIC_SIDECAR_LOG_LEVEL": app_settings.DYNAMIC_SERVICES.DYNAMIC_SIDECAR.DYNAMIC_SIDECAR_LOG_LEVEL,
        "POSTGRES_DB": f"{app_settings.POSTGRES.POSTGRES_DB}",
        "POSTGRES_ENDPOINT": f"{app_settings.POSTGRES.POSTGRES_HOST}:{app_settings.POSTGRES.POSTGRES_PORT}",
        "POSTGRES_HOST": f"{app_settings.POSTGRES.POSTGRES_HOST}",
        "POSTGRES_PASSWORD": f"{app_settings.POSTGRES.POSTGRES_PASSWORD.get_secret_value()}",
        "POSTGRES_PORT": f"{app_settings.POSTGRES.POSTGRES_PORT}",
        "POSTGRES_USER": f"{app_settings.POSTGRES.POSTGRES_USER}",
        "R_CLONE_ENABLED": f"{r_clone_settings.R_CLONE_ENABLED}",
        "R_CLONE_PROVIDER": r_clone_settings.R_CLONE_PROVIDER,
        "RABBIT_HOST": f"{rabbit_settings.RABBIT_HOST}",
        "RABBIT_PASSWORD": f"{rabbit_settings.RABBIT_PASSWORD.get_secret_value()}",
        "RABBIT_PORT": f"{rabbit_settings.RABBIT_PORT}",
        "RABBIT_USER": f"{rabbit_settings.RABBIT_USER}",
        "REGISTRY_AUTH": f"{registry_settings.REGISTRY_AUTH}",
        "REGISTRY_PATH": f"{registry_settings.REGISTRY_PATH}",
        "REGISTRY_PW": f"{registry_settings.REGISTRY_PW.get_secret_value()}",
        "REGISTRY_SSL": f"{registry_settings.REGISTRY_SSL}",
        "REGISTRY_URL": f"{registry_settings.REGISTRY_URL}",
        "REGISTRY_USER": f"{registry_settings.REGISTRY_USER}",
        "S3_ACCESS_KEY": r_clone_settings.R_CLONE_S3.S3_ACCESS_KEY,
        "S3_BUCKET_NAME": r_clone_settings.R_CLONE_S3.S3_BUCKET_NAME,
        "S3_ENDPOINT": r_clone_settings.R_CLONE_S3.S3_ENDPOINT,
        "S3_SECRET_KEY": r_clone_settings.R_CLONE_S3.S3_SECRET_KEY,
        "S3_SECURE": f"{r_clone_settings.R_CLONE_S3.S3_SECURE}",
        "SC_BOOT_MODE": f"{app_settings.DYNAMIC_SERVICES.DYNAMIC_SIDECAR.DYNAMIC_SIDECAR_SC_BOOT_MODE}",
        "SSL_CERT_FILE": f"{app_settings.DIRECTOR_V2_SELF_SIGNED_SSL_FILENAME}",
        # For background info on this special env-var above, see
        # - https://stackoverflow.com/questions/31448854/how-to-force-requests-use-the-certificates-on-my-ubuntu-system#comment78596389_37447847#
        # - https://stackoverflow.com/questions/31448854/how-to-force-requests-use-the-certificates-on-my-ubuntu-system#comment78596389_37447847
        "SIMCORE_HOST_NAME": scheduler_data.service_name,
        "STORAGE_HOST": app_settings.DIRECTOR_V2_STORAGE.STORAGE_HOST,
        "STORAGE_PORT": f"{app_settings.DIRECTOR_V2_STORAGE.STORAGE_PORT}",
    }


def get_dynamic_sidecar_spec(
    scheduler_data: SchedulerData,
    dynamic_sidecar_settings: DynamicSidecarSettings,
    swarm_network_id: str,
    settings: SimcoreServiceSettingsLabel,
    app_settings: AppSettings,
) -> AioDockerServiceSpec:
    """
    The dynamic-sidecar is responsible for managing the lifecycle
    of the dynamic service. The director-v2 directly coordinates with
    the dynamic-sidecar for this purpose.

    returns: the compose the request body for service creation
    SEE https://docs.docker.com/engine/api/v1.41/#tag/Service/operation/ServiceCreate
    """
    compose_namespace = get_compose_namespace(scheduler_data.node_uuid)

    # MOUNTS -----------
    mounts = [
        # docker socket needed to use the docker api
        {
            "Source": "/var/run/docker.sock",
            "Target": "/var/run/docker.sock",
            "Type": "bind",
        },
        DynamicSidecarVolumesPathsResolver.mount_shared_store(
            swarm_stack_name=dynamic_sidecar_settings.SWARM_STACK_NAME,
            node_uuid=scheduler_data.node_uuid,
            run_id=scheduler_data.run_id,
            project_id=scheduler_data.project_id,
            user_id=scheduler_data.user_id,
        ),
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
                path=path_to_mount,
                node_uuid=scheduler_data.node_uuid,
                run_id=scheduler_data.run_id,
                project_id=scheduler_data.project_id,
                user_id=scheduler_data.user_id,
            )
        )
    # state paths now get mounted via different driver and are synced to s3 automatically
    for path_to_mount in scheduler_data.paths_mapping.state_paths:
        # for now only enable this with dev features enabled
        if app_settings.DIRECTOR_V2_DEV_FEATURE_R_CLONE_MOUNTS_ENABLED:
            mounts.append(
                DynamicSidecarVolumesPathsResolver.mount_r_clone(
                    swarm_stack_name=dynamic_sidecar_settings.SWARM_STACK_NAME,
                    path=path_to_mount,
                    node_uuid=scheduler_data.node_uuid,
                    run_id=scheduler_data.run_id,
                    project_id=scheduler_data.project_id,
                    user_id=scheduler_data.user_id,
                    r_clone_settings=dynamic_sidecar_settings.DYNAMIC_SIDECAR_R_CLONE_SETTINGS,
                )
            )
        else:
            mounts.append(
                DynamicSidecarVolumesPathsResolver.mount_entry(
                    swarm_stack_name=dynamic_sidecar_settings.SWARM_STACK_NAME,
                    path=path_to_mount,
                    node_uuid=scheduler_data.node_uuid,
                    run_id=scheduler_data.run_id,
                    project_id=scheduler_data.project_id,
                    user_id=scheduler_data.user_id,
                )
            )

    if dynamic_sidecar_path := dynamic_sidecar_settings.DYNAMIC_SIDECAR_MOUNT_PATH_DEV:
        # Settings validators guarantees that this never happens in production mode
        assert (
            dynamic_sidecar_settings.DYNAMIC_SIDECAR_SC_BOOT_MODE
            != BootModeEnum.PRODUCTION
        )

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

    # PORTS -----------
    ports = []  # expose this service on an empty port
    if dynamic_sidecar_settings.DYNAMIC_SIDECAR_EXPOSE_PORT:
        ports.append(
            # server port
            {
                "Protocol": "tcp",
                "TargetPort": dynamic_sidecar_settings.DYNAMIC_SIDECAR_PORT,
            }
        )

        if dynamic_sidecar_settings.DYNAMIC_SIDECAR_SC_BOOT_MODE == BootModeEnum.DEBUG:
            ports.append(
                # debugger port
                {
                    "Protocol": "tcp",
                    "TargetPort": app_settings.DIRECTOR_V2_REMOTE_DEBUG_PORT,
                }
            )

    #  -----------
    create_service_params = {
        "endpoint_spec": {"Ports": ports} if ports else {},
        "labels": {
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
        "networks": [{"Target": swarm_network_id}],
        "task_template": {
            "ContainerSpec": {
                "Env": _get_environment_variables(
                    compose_namespace, scheduler_data, app_settings
                ),
                "Hosts": [],
                "Image": dynamic_sidecar_settings.DYNAMIC_SIDECAR_IMAGE,
                "Init": True,
                "Labels": {
                    # NOTE: these labels get on the tasks and that is also useful to trace
                    "user_id": f"{scheduler_data.user_id}",
                    "study_id": f"{scheduler_data.project_id}",
                    "uuid": f"{scheduler_data.node_uuid}",
                },
                "Mounts": mounts,
                "Secrets": [
                    {
                        "SecretID": app_settings.DIRECTOR_V2_SELF_SIGNED_SSL_SECRET_ID,
                        "SecretName": app_settings.DIRECTOR_V2_SELF_SIGNED_SSL_SECRET_NAME,
                        "File": {
                            "Name": app_settings.DIRECTOR_V2_SELF_SIGNED_SSL_FILENAME,
                            "Mode": 444,
                            "UID": "0",
                            "GID": "0",
                        },
                    }
                ]
                if (
                    app_settings.DIRECTOR_V2_SELF_SIGNED_SSL_FILENAME
                    and app_settings.DIRECTOR_V2_SELF_SIGNED_SSL_SECRET_ID
                    and app_settings.DIRECTOR_V2_SELF_SIGNED_SSL_SECRET_NAME
                    and app_settings.DIRECTOR_V2_DEV_FEATURES_ENABLED
                )
                else None,
            },
            "Placement": {
                "Constraints": deepcopy(
                    app_settings.DIRECTOR_V2_SERVICES_CUSTOM_CONSTRAINTS
                )
            },
            "RestartPolicy": DOCKER_CONTAINER_SPEC_RESTART_POLICY_DEFAULTS,
            # this will get overwritten
            "Resources": {
                "Limits": {"NanoCPUs": 0, "MemoryBytes": 0},
                "Reservation": {"NanoCPUs": 0, "MemoryBytes": 0},
            },
        },
    }

    update_service_params_from_settings(
        labels_service_settings=settings,
        create_service_params=create_service_params,
    )

    return AioDockerServiceSpec.parse_obj(create_service_params)
