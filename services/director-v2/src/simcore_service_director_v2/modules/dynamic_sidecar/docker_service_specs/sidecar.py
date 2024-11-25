import logging
from copy import deepcopy
from typing import Any, NamedTuple

from common_library.json_serialization import json_dumps
from common_library.serialization import model_dump_with_secrets
from models_library.aiodocker_api import AioDockerServiceSpec
from models_library.basic_types import BootModeEnum, PortInt
from models_library.callbacks_mapping import CallbacksMapping
from models_library.docker import (
    DOCKER_TASK_EC2_INSTANCE_TYPE_PLACEMENT_CONSTRAINT_KEY,
    DockerLabelKey,
    DockerPlacementConstraint,
    StandardSimcoreDockerLabels,
    to_simcore_runtime_docker_label_key,
)
from models_library.resource_tracker import HardwareInfo
from models_library.service_settings_labels import SimcoreServiceSettingsLabel
from pydantic import ByteSize, TypeAdapter
from servicelib.rabbitmq import RabbitMQRPCClient
from servicelib.rabbitmq.rpc_interfaces.efs_guardian import efs_manager
from servicelib.utils import unused_port

from ....constants import DYNAMIC_SIDECAR_SCHEDULER_DATA_LABEL
from ....core.dynamic_services_settings.scheduler import (
    DynamicServicesSchedulerSettings,
)
from ....core.dynamic_services_settings.sidecar import DynamicSidecarSettings
from ....core.settings import AppSettings
from ....models.dynamic_services_scheduler import SchedulerData
from ....modules.db.repositories.groups_extra_properties import UserExtraProperties
from .._namespace import get_compose_namespace
from ..volumes import DynamicSidecarVolumesPathsResolver
from ._constants import DOCKER_CONTAINER_SPEC_RESTART_POLICY_DEFAULTS
from .settings import (
    extract_service_port_from_settings,
    update_service_params_from_settings,
)

_logger = logging.getLogger(__name__)


def extract_service_port_service_settings(
    settings: SimcoreServiceSettingsLabel,
) -> PortInt:
    return extract_service_port_from_settings(settings)


class _StorageConfig(NamedTuple):
    host: str
    port: str
    username: str
    password: str
    secure: str


def _get_storage_config(app_settings: AppSettings) -> _StorageConfig:
    host: str = app_settings.DIRECTOR_V2_STORAGE.STORAGE_HOST
    port: str = f"{app_settings.DIRECTOR_V2_STORAGE.STORAGE_PORT}"
    username: str = "null"
    password: str = "null"
    secure: str = "0"

    storage_auth_settings = app_settings.DIRECTOR_V2_NODE_PORTS_STORAGE_AUTH

    if storage_auth_settings and storage_auth_settings.auth_required:
        host = storage_auth_settings.STORAGE_HOST
        port = f"{storage_auth_settings.STORAGE_PORT}"
        assert storage_auth_settings.STORAGE_USERNAME  # nosec
        username = storage_auth_settings.STORAGE_USERNAME
        assert storage_auth_settings.STORAGE_PASSWORD  # nosec
        password = storage_auth_settings.STORAGE_PASSWORD.get_secret_value()
        secure = "1" if storage_auth_settings.STORAGE_SECURE else "0"

    return _StorageConfig(
        host=host,
        port=port,
        username=username,
        password=password,
        secure=secure,
    )


def _get_environment_variables(
    compose_namespace: str,
    scheduler_data: SchedulerData,
    app_settings: AppSettings,
    *,
    allow_internet_access: bool,
    metrics_collection_allowed: bool,
    telemetry_enabled: bool,
) -> dict[str, str]:
    rabbit_settings = app_settings.DIRECTOR_V2_RABBITMQ
    r_clone_settings = (
        app_settings.DYNAMIC_SERVICES.DYNAMIC_SIDECAR.DYNAMIC_SIDECAR_R_CLONE_SETTINGS
    )
    dy_sidecar_aws_s3_cli_settings = None
    if (
        app_settings.DYNAMIC_SERVICES.DYNAMIC_SIDECAR.DYNAMIC_SIDECAR_AWS_S3_CLI_SETTINGS
        and app_settings.DYNAMIC_SERVICES.DYNAMIC_SIDECAR.DYNAMIC_SIDECAR_AWS_S3_CLI_SETTINGS.AWS_S3_CLI_S3
    ):
        dy_sidecar_aws_s3_cli_settings = json_dumps(
            model_dump_with_secrets(
                app_settings.DYNAMIC_SERVICES.DYNAMIC_SIDECAR.DYNAMIC_SIDECAR_AWS_S3_CLI_SETTINGS,
                show_secrets=True,
            )
        )

    state_exclude = set()
    if scheduler_data.paths_mapping.state_exclude is not None:
        state_exclude = scheduler_data.paths_mapping.state_exclude

    callbacks_mapping: CallbacksMapping = scheduler_data.callbacks_mapping

    if not metrics_collection_allowed:
        _logger.info(
            "user=%s disabled metrics collection, disable prometheus metrics for node_id=%s",
            scheduler_data.user_id,
            scheduler_data.node_uuid,
        )
        callbacks_mapping.metrics = None

    storage_config = _get_storage_config(app_settings)

    envs: dict[str, str] = {
        # These environments will be captured by
        # services/dynamic-sidecar/src/simcore_service_dynamic_sidecar/core/settings.py::ApplicationSettings
        #
        "DY_SIDECAR_NODE_ID": f"{scheduler_data.node_uuid}",
        "DY_SIDECAR_PATH_INPUTS": f"{scheduler_data.paths_mapping.inputs_path}",
        "DY_SIDECAR_PATH_OUTPUTS": f"{scheduler_data.paths_mapping.outputs_path}",
        "DY_SIDECAR_PROJECT_ID": f"{scheduler_data.project_id}",
        "DY_SIDECAR_RUN_ID": scheduler_data.run_id,
        "DY_SIDECAR_USER_SERVICES_HAVE_INTERNET_ACCESS": f"{allow_internet_access}",
        "DY_SIDECAR_SYSTEM_MONITOR_TELEMETRY_ENABLE": f"{telemetry_enabled}",
        "DY_SIDECAR_STATE_EXCLUDE": json_dumps(f"{x}" for x in state_exclude),
        "DY_SIDECAR_CALLBACKS_MAPPING": callbacks_mapping.model_dump_json(),
        "DY_SIDECAR_STATE_PATHS": json_dumps(
            f"{x}" for x in scheduler_data.paths_mapping.state_paths
        ),
        "DY_SIDECAR_USER_ID": f"{scheduler_data.user_id}",
        "DY_SIDECAR_AWS_S3_CLI_SETTINGS": dy_sidecar_aws_s3_cli_settings or "null",
        "DYNAMIC_SIDECAR_COMPOSE_NAMESPACE": compose_namespace,
        "DYNAMIC_SIDECAR_LOG_LEVEL": app_settings.DYNAMIC_SERVICES.DYNAMIC_SIDECAR.DYNAMIC_SIDECAR_LOG_LEVEL,
        "DY_SIDECAR_LOG_FORMAT_LOCAL_DEV_ENABLED": f"{app_settings.DIRECTOR_V2_LOG_FORMAT_LOCAL_DEV_ENABLED}",
        "POSTGRES_DB": f"{app_settings.POSTGRES.POSTGRES_DB}",
        "POSTGRES_ENDPOINT": f"{app_settings.POSTGRES.POSTGRES_HOST}:{app_settings.POSTGRES.POSTGRES_PORT}",
        "POSTGRES_HOST": f"{app_settings.POSTGRES.POSTGRES_HOST}",
        "POSTGRES_PASSWORD": f"{app_settings.POSTGRES.POSTGRES_PASSWORD.get_secret_value()}",
        "POSTGRES_PORT": f"{app_settings.POSTGRES.POSTGRES_PORT}",
        "POSTGRES_USER": f"{app_settings.POSTGRES.POSTGRES_USER}",
        "R_CLONE_PROVIDER": r_clone_settings.R_CLONE_PROVIDER,
        "R_CLONE_OPTION_TRANSFERS": f"{r_clone_settings.R_CLONE_OPTION_TRANSFERS}",
        "R_CLONE_OPTION_RETRIES": f"{r_clone_settings.R_CLONE_OPTION_RETRIES}",
        "R_CLONE_OPTION_BUFFER_SIZE": r_clone_settings.R_CLONE_OPTION_BUFFER_SIZE,
        "RABBIT_HOST": f"{rabbit_settings.RABBIT_HOST}",
        "RABBIT_PASSWORD": f"{rabbit_settings.RABBIT_PASSWORD.get_secret_value()}",
        "RABBIT_PORT": f"{rabbit_settings.RABBIT_PORT}",
        "RABBIT_USER": f"{rabbit_settings.RABBIT_USER}",
        "RABBIT_SECURE": f"{rabbit_settings.RABBIT_SECURE}",
        "DY_DEPLOYMENT_REGISTRY_SETTINGS": (
            json_dumps(
                model_dump_with_secrets(
                    app_settings.DIRECTOR_V2_DOCKER_REGISTRY,
                    show_secrets=True,
                    exclude={"resolved_registry_url", "api_url"},
                )
            )
        ),
        "DY_DOCKER_HUB_REGISTRY_SETTINGS": (
            json_dumps(
                model_dump_with_secrets(
                    app_settings.DIRECTOR_V2_DOCKER_HUB_REGISTRY,
                    show_secrets=True,
                    exclude={"resolved_registry_url", "api_url"},
                )
            )
            if app_settings.DIRECTOR_V2_DOCKER_HUB_REGISTRY
            else "null"
        ),
        "S3_ACCESS_KEY": r_clone_settings.R_CLONE_S3.S3_ACCESS_KEY,
        "S3_BUCKET_NAME": r_clone_settings.R_CLONE_S3.S3_BUCKET_NAME,
        "S3_REGION": r_clone_settings.R_CLONE_S3.S3_REGION,
        "S3_SECRET_KEY": r_clone_settings.R_CLONE_S3.S3_SECRET_KEY,
        "SC_BOOT_MODE": f"{app_settings.DYNAMIC_SERVICES.DYNAMIC_SIDECAR.DYNAMIC_SIDECAR_SC_BOOT_MODE}",
        "SSL_CERT_FILE": app_settings.DIRECTOR_V2_SELF_SIGNED_SSL_FILENAME,
        "DYNAMIC_SIDECAR_TRACING": (
            app_settings.DIRECTOR_V2_TRACING.json()
            if app_settings.DIRECTOR_V2_TRACING
            else "null"
        ),
        # For background info on this special env-var above, see
        # - https://stackoverflow.com/questions/31448854/how-to-force-requests-use-the-certificates-on-my-ubuntu-system#comment78596389_37447847
        "SIMCORE_HOST_NAME": scheduler_data.service_name,
        "STORAGE_HOST": storage_config.host,
        "STORAGE_PASSWORD": storage_config.password,
        "STORAGE_PORT": storage_config.port,
        "STORAGE_SECURE": storage_config.secure,
        "STORAGE_USERNAME": storage_config.username,
        "DY_SIDECAR_SERVICE_KEY": scheduler_data.key,
        "DY_SIDECAR_SERVICE_VERSION": scheduler_data.version,
        "DY_SIDECAR_USER_PREFERENCES_PATH": f"{scheduler_data.user_preferences_path}",
        "DY_SIDECAR_PRODUCT_NAME": f"{scheduler_data.product_name}",
        "NODE_PORTS_400_REQUEST_TIMEOUT_ATTEMPTS": f"{app_settings.DIRECTOR_V2_NODE_PORTS_400_REQUEST_TIMEOUT_ATTEMPTS}",
    }
    if r_clone_settings.R_CLONE_S3.S3_ENDPOINT is not None:
        envs["S3_ENDPOINT"] = f"{r_clone_settings.R_CLONE_S3.S3_ENDPOINT}"
    return envs


def get_prometheus_service_labels(
    prometheus_service_labels: dict[str, str], callbacks_mapping: CallbacksMapping
) -> dict[str, str]:
    # NOTE: if the service must be scraped it will expose a /metrics endpoint
    # these labels instruct prometheus to scrape it.
    enable_prometheus_scraping = callbacks_mapping.metrics is not None
    return prometheus_service_labels if enable_prometheus_scraping else {}


def get_prometheus_monitoring_networks(
    prometheus_networks: list[str], callbacks_mapping: CallbacksMapping
) -> list[dict[str, str]]:
    return (
        []
        if callbacks_mapping.metrics is None
        else [{"Target": network_name} for network_name in prometheus_networks]
    )


async def _get_mounts(
    *,
    scheduler_data: SchedulerData,
    dynamic_sidecar_settings: DynamicSidecarSettings,
    dynamic_services_scheduler_settings: DynamicServicesSchedulerSettings,
    app_settings: AppSettings,
    has_quota_support: bool,
    rpc_client: RabbitMQRPCClient,
    is_efs_enabled: bool,
) -> list[dict[str, Any]]:
    mounts: list[dict[str, Any]] = [
        # docker socket needed to use the docker api
        {
            "Source": "/var/run/docker.sock",
            "Target": "/var/run/docker.sock",
            "Type": "bind",
        },
        DynamicSidecarVolumesPathsResolver.mount_shared_store(
            swarm_stack_name=dynamic_services_scheduler_settings.SWARM_STACK_NAME,
            node_uuid=scheduler_data.node_uuid,
            run_id=scheduler_data.run_id,
            project_id=scheduler_data.project_id,
            user_id=scheduler_data.user_id,
            has_quota_support=has_quota_support,
        ),
    ]

    volume_size_limits = (
        scheduler_data.paths_mapping.volume_size_limits or {}
        if has_quota_support
        else {}
    )

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
        mounts.append(  # noqa: PERF401
            DynamicSidecarVolumesPathsResolver.mount_entry(
                swarm_stack_name=dynamic_services_scheduler_settings.SWARM_STACK_NAME,
                path=path_to_mount,
                node_uuid=scheduler_data.node_uuid,
                run_id=scheduler_data.run_id,
                project_id=scheduler_data.project_id,
                user_id=scheduler_data.user_id,
                volume_size_limit=volume_size_limits.get(f"{path_to_mount}"),
            )
        )

    # state paths now get mounted via different driver and are synced to s3 automatically
    for path_to_mount in scheduler_data.paths_mapping.state_paths:
        if is_efs_enabled:
            assert dynamic_sidecar_settings.DYNAMIC_SIDECAR_EFS_SETTINGS  # nosec

            _storage_directory_name = DynamicSidecarVolumesPathsResolver.volume_name(
                path_to_mount
            ).strip("_")
            await efs_manager.create_project_specific_data_dir(
                rpc_client,
                project_id=scheduler_data.project_id,
                node_id=scheduler_data.node_uuid,
                storage_directory_name=_storage_directory_name,
            )
            mounts.append(
                DynamicSidecarVolumesPathsResolver.mount_efs(
                    swarm_stack_name=dynamic_services_scheduler_settings.SWARM_STACK_NAME,
                    path=path_to_mount,
                    node_uuid=scheduler_data.node_uuid,
                    run_id=scheduler_data.run_id,
                    project_id=scheduler_data.project_id,
                    user_id=scheduler_data.user_id,
                    efs_settings=dynamic_sidecar_settings.DYNAMIC_SIDECAR_EFS_SETTINGS,
                    storage_directory_name=_storage_directory_name,
                )
            )
        # for now only enable this with dev features enabled
        elif app_settings.DIRECTOR_V2_DEV_FEATURE_R_CLONE_MOUNTS_ENABLED:
            mounts.append(
                DynamicSidecarVolumesPathsResolver.mount_r_clone(
                    swarm_stack_name=dynamic_services_scheduler_settings.SWARM_STACK_NAME,
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
                    swarm_stack_name=dynamic_services_scheduler_settings.SWARM_STACK_NAME,
                    path=path_to_mount,
                    node_uuid=scheduler_data.node_uuid,
                    run_id=scheduler_data.run_id,
                    project_id=scheduler_data.project_id,
                    user_id=scheduler_data.user_id,
                    volume_size_limit=volume_size_limits.get(f"{path_to_mount}"),
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

    if scheduler_data.user_preferences_path:
        mounts.append(
            DynamicSidecarVolumesPathsResolver.mount_user_preferences(
                user_preferences_path=scheduler_data.user_preferences_path,
                swarm_stack_name=dynamic_services_scheduler_settings.SWARM_STACK_NAME,
                node_uuid=scheduler_data.node_uuid,
                run_id=scheduler_data.run_id,
                project_id=scheduler_data.project_id,
                user_id=scheduler_data.user_id,
                has_quota_support=has_quota_support,
            )
        )
    return mounts


def _get_ports(
    *, dynamic_sidecar_settings: DynamicSidecarSettings, app_settings: AppSettings
) -> list[dict[str, Any]]:
    ports: list[dict[str, Any]] = []  # expose this service on an empty port
    if dynamic_sidecar_settings.DYNAMIC_SIDECAR_EXPOSE_PORT:
        ports.append(
            # server port
            {
                "Protocol": "tcp",
                "TargetPort": dynamic_sidecar_settings.DYNAMIC_SIDECAR_PORT,
                "PublishedPort": unused_port(),
                "PublishMode": "host",
            }
        )

        if dynamic_sidecar_settings.DYNAMIC_SIDECAR_SC_BOOT_MODE == BootModeEnum.DEBUG:
            ports.append(
                # debugger port
                {
                    "Protocol": "tcp",
                    "TargetPort": app_settings.DIRECTOR_V2_REMOTE_DEBUGGING_PORT,
                    "PublishedPort": unused_port(),
                    "PublishMode": "host",
                }
            )
    return ports


async def get_dynamic_sidecar_spec(  # pylint:disable=too-many-arguments# noqa: PLR0913
    scheduler_data: SchedulerData,
    dynamic_sidecar_settings: DynamicSidecarSettings,
    dynamic_services_scheduler_settings: DynamicServicesSchedulerSettings,
    swarm_network_id: str,
    settings: SimcoreServiceSettingsLabel,
    app_settings: AppSettings,
    *,
    has_quota_support: bool,
    hardware_info: HardwareInfo | None,
    metrics_collection_allowed: bool,
    user_extra_properties: UserExtraProperties,
    rpc_client: RabbitMQRPCClient,
) -> AioDockerServiceSpec:
    """
    The dynamic-sidecar is responsible for managing the lifecycle
    of the dynamic service. The director-v2 directly coordinates with
    the dynamic-sidecar for this purpose.

    returns: the compose the request body for service creation
    SEE https://docs.docker.com/engine/api/v1.41/#tag/Service/operation/ServiceCreate
    """
    compose_namespace = get_compose_namespace(scheduler_data.node_uuid)

    mounts = await _get_mounts(
        scheduler_data=scheduler_data,
        dynamic_services_scheduler_settings=dynamic_services_scheduler_settings,
        dynamic_sidecar_settings=dynamic_sidecar_settings,
        app_settings=app_settings,
        has_quota_support=has_quota_support,
        rpc_client=rpc_client,
        is_efs_enabled=user_extra_properties.is_efs_enabled,
    )

    ports = _get_ports(
        dynamic_sidecar_settings=dynamic_sidecar_settings, app_settings=app_settings
    )

    standard_simcore_docker_labels: dict[
        DockerLabelKey, str
    ] = StandardSimcoreDockerLabels(
        user_id=scheduler_data.user_id,
        project_id=scheduler_data.project_id,
        node_id=scheduler_data.node_uuid,
        product_name=scheduler_data.product_name,
        simcore_user_agent=scheduler_data.request_simcore_user_agent,
        swarm_stack_name=dynamic_services_scheduler_settings.SWARM_STACK_NAME,
        memory_limit=ByteSize(0),  # this should get overwritten
        cpu_limit=0,  # this should get overwritten
    ).to_simcore_runtime_docker_labels()

    service_labels: dict[str, str] = (
        {
            DYNAMIC_SIDECAR_SCHEDULER_DATA_LABEL: scheduler_data.as_label_data(),
            to_simcore_runtime_docker_label_key("service_key"): scheduler_data.key,
            to_simcore_runtime_docker_label_key(
                "service_version"
            ): scheduler_data.version,
        }
        | get_prometheus_service_labels(
            dynamic_services_scheduler_settings.DYNAMIC_SIDECAR_PROMETHEUS_SERVICE_LABELS,
            scheduler_data.callbacks_mapping,
        )
        | standard_simcore_docker_labels
    )

    placement_settings = (
        app_settings.DYNAMIC_SERVICES.DYNAMIC_SIDECAR.DYNAMIC_SIDECAR_PLACEMENT_SETTINGS
    )
    placement_constraints = deepcopy(
        placement_settings.DIRECTOR_V2_SERVICES_CUSTOM_CONSTRAINTS
    )
    # if service has a pricing plan apply constraints for autoscaling
    if hardware_info and len(hardware_info.aws_ec2_instances) == 1:
        ec2_instance_type: str = hardware_info.aws_ec2_instances[0]
        placement_constraints.append(
            TypeAdapter(DockerPlacementConstraint).validate_python(
                f"node.labels.{DOCKER_TASK_EC2_INSTANCE_TYPE_PLACEMENT_CONSTRAINT_KEY}=={ec2_instance_type}",
            )
        )

    placement_substitutions: dict[
        str, DockerPlacementConstraint
    ] = (
        placement_settings.DIRECTOR_V2_GENERIC_RESOURCE_PLACEMENT_CONSTRAINTS_SUBSTITUTIONS
    )
    for image_resources in scheduler_data.service_resources.values():
        for resource_name in image_resources.resources:
            if resource_name in placement_substitutions:
                placement_constraints.append(placement_substitutions[resource_name])

    #  -----------
    create_service_params = {
        "endpoint_spec": {"Ports": ports} if ports else {},
        "labels": service_labels,
        "name": scheduler_data.service_name,
        "networks": [
            {"Target": swarm_network_id},
            *get_prometheus_monitoring_networks(
                dynamic_services_scheduler_settings.DYNAMIC_SIDECAR_PROMETHEUS_MONITORING_NETWORKS,
                scheduler_data.callbacks_mapping,
            ),
        ],
        "task_template": {
            "ContainerSpec": {
                "Env": _get_environment_variables(
                    compose_namespace,
                    scheduler_data,
                    app_settings,
                    allow_internet_access=user_extra_properties.is_internet_enabled,
                    metrics_collection_allowed=metrics_collection_allowed,
                    telemetry_enabled=user_extra_properties.is_telemetry_enabled,
                ),
                "Hosts": [],
                "Image": dynamic_sidecar_settings.DYNAMIC_SIDECAR_IMAGE,
                "Init": True,
                "Labels": standard_simcore_docker_labels,
                "Mounts": mounts,
                "Secrets": (
                    [
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
                    else None
                ),
            },
            "Placement": {"Constraints": placement_constraints},
            "RestartPolicy": DOCKER_CONTAINER_SPEC_RESTART_POLICY_DEFAULTS,
            # this will get overwritten
            "Resources": {
                "Limits": {"NanoCPUs": 0, "MemoryBytes": 0},
                "Reservation": {"NanoCPUs": 0, "MemoryBytes": 0},
            },
        },
    }

    if dynamic_sidecar_settings.DYNAMIC_SIDECAR_ENDPOINT_SPECS_MODE_DNSRR_ENABLED:
        create_service_params["endpoint_spec"] = {"Mode": "dnsrr"}

    update_service_params_from_settings(
        labels_service_settings=settings,
        create_service_params=create_service_params,
    )

    return AioDockerServiceSpec.model_validate(create_service_params)
