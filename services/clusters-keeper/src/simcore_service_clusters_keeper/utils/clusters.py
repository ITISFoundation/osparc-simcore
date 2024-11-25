import base64
import datetime
import functools
import json
from pathlib import Path
from typing import Any, Final

import arrow
import yaml
from aws_library.ec2 import EC2InstanceBootSpecific, EC2InstanceData, EC2Tags
from aws_library.ec2._models import CommandStr
from fastapi.encoders import jsonable_encoder
from models_library.api_schemas_clusters_keeper.clusters import (
    ClusterState,
    OnDemandCluster,
)
from models_library.clusters import InternalClusterAuthentication, TLSAuthentication
from models_library.users import UserID
from models_library.wallets import WalletID
from types_aiobotocore_ec2.literals import InstanceStateNameType

from .._meta import PACKAGE_DATA_FOLDER
from ..core.settings import ApplicationSettings
from .dask import get_scheduler_url

_DOCKER_COMPOSE_FILE_NAME: Final[str] = "docker-compose.yml"
_PROMETHEUS_FILE_NAME: Final[str] = "prometheus.yml"
_PROMETHEUS_WEB_FILE_NAME: Final[str] = "prometheus-web.yml"
_HOST_DOCKER_COMPOSE_PATH: Final[Path] = Path(f"/{_DOCKER_COMPOSE_FILE_NAME}")
_HOST_PROMETHEUS_PATH: Final[Path] = Path(f"/{_PROMETHEUS_FILE_NAME}")
_HOST_PROMETHEUS_WEB_PATH: Final[Path] = Path(f"/{_PROMETHEUS_WEB_FILE_NAME}")
_HOST_CERTIFICATES_BASE_PATH: Final[Path] = Path("/.dask-sidecar-certificates")
_HOST_TLS_CA_FILE_PATH: Final[Path] = _HOST_CERTIFICATES_BASE_PATH / "tls_dask_ca.pem"
_HOST_TLS_CERT_FILE_PATH: Final[Path] = (
    _HOST_CERTIFICATES_BASE_PATH / "tls_dask_cert.pem"
)
_HOST_TLS_KEY_FILE_PATH: Final[Path] = _HOST_CERTIFICATES_BASE_PATH / "tls_dask_key.pem"


def _base_64_encode(file: Path) -> str:
    assert file.exists()  # nosec
    with file.open("rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


@functools.lru_cache
def _docker_compose_yml_base64_encoded() -> str:
    file_path = PACKAGE_DATA_FOLDER / _DOCKER_COMPOSE_FILE_NAME
    return _base_64_encode(file_path)


@functools.lru_cache
def _prometheus_yml_base64_encoded() -> str:
    file_path = PACKAGE_DATA_FOLDER / _PROMETHEUS_FILE_NAME
    return _base_64_encode(file_path)


@functools.lru_cache
def _prometheus_basic_auth_yml_base64_encoded(
    prometheus_username: str, prometheus_password: str
) -> str:
    web_config = {"basic_auth_users": {prometheus_username: prometheus_password}}
    yaml_content = yaml.safe_dump(web_config)
    base64_bytes = base64.b64encode(yaml_content.encode("utf-8"))
    return base64_bytes.decode("utf-8")


def _prepare_environment_variables(
    app_settings: ApplicationSettings,
    *,
    cluster_machines_name_prefix: str,
    additional_custom_tags: EC2Tags,
) -> list[str]:
    assert app_settings.CLUSTERS_KEEPER_EC2_ACCESS  # nosec
    assert app_settings.CLUSTERS_KEEPER_WORKERS_EC2_INSTANCES  # nosec

    def _convert_to_env_list(entries: list[Any]) -> str:
        entries_as_str = ",".join(rf"\"{k}\"" for k in entries)
        return f"[{entries_as_str}]"

    def _convert_to_env_dict(entries: dict[str, Any]) -> str:
        return f"'{json.dumps(jsonable_encoder(entries))}'"

    return [
        f"CLUSTERS_KEEPER_EC2_ACCESS_KEY_ID={app_settings.CLUSTERS_KEEPER_EC2_ACCESS.EC2_ACCESS_KEY_ID}",
        f"CLUSTERS_KEEPER_EC2_ENDPOINT={app_settings.CLUSTERS_KEEPER_EC2_ACCESS.EC2_ENDPOINT or 'null'}",
        f"CLUSTERS_KEEPER_EC2_REGION_NAME={app_settings.CLUSTERS_KEEPER_EC2_ACCESS.EC2_REGION_NAME}",
        f"CLUSTERS_KEEPER_EC2_SECRET_ACCESS_KEY={app_settings.CLUSTERS_KEEPER_EC2_ACCESS.EC2_SECRET_ACCESS_KEY}",
        f"DASK_NTHREADS={app_settings.CLUSTERS_KEEPER_DASK_NTHREADS or ''}",
        f"DASK_TLS_CA_FILE={_HOST_TLS_CA_FILE_PATH}",
        f"DASK_TLS_CERT={_HOST_TLS_CERT_FILE_PATH}",
        f"DASK_TLS_KEY={_HOST_TLS_KEY_FILE_PATH}",
        f"DASK_WORKER_SATURATION={app_settings.CLUSTERS_KEEPER_DASK_WORKER_SATURATION}",
        f"DOCKER_IMAGE_TAG={app_settings.CLUSTERS_KEEPER_COMPUTATIONAL_BACKEND_DOCKER_IMAGE_TAG}",
        f"EC2_INSTANCES_NAME_PREFIX={cluster_machines_name_prefix}",
        f"LOG_LEVEL={app_settings.LOG_LEVEL}",
        f"WORKERS_EC2_INSTANCES_ALLOWED_TYPES={_convert_to_env_dict(app_settings.CLUSTERS_KEEPER_WORKERS_EC2_INSTANCES.WORKERS_EC2_INSTANCES_ALLOWED_TYPES)}",
        f"WORKERS_EC2_INSTANCES_CUSTOM_TAGS={_convert_to_env_dict(app_settings.CLUSTERS_KEEPER_WORKERS_EC2_INSTANCES.WORKERS_EC2_INSTANCES_CUSTOM_TAGS | additional_custom_tags)}",
        f"WORKERS_EC2_INSTANCES_KEY_NAME={app_settings.CLUSTERS_KEEPER_WORKERS_EC2_INSTANCES.WORKERS_EC2_INSTANCES_KEY_NAME}",
        f"WORKERS_EC2_INSTANCES_MAX_INSTANCES={app_settings.CLUSTERS_KEEPER_WORKERS_EC2_INSTANCES.WORKERS_EC2_INSTANCES_MAX_INSTANCES}",
        f"WORKERS_EC2_INSTANCES_SECURITY_GROUP_IDS={_convert_to_env_list(app_settings.CLUSTERS_KEEPER_WORKERS_EC2_INSTANCES.WORKERS_EC2_INSTANCES_SECURITY_GROUP_IDS)}",
        f"WORKERS_EC2_INSTANCES_SUBNET_ID={app_settings.CLUSTERS_KEEPER_WORKERS_EC2_INSTANCES.WORKERS_EC2_INSTANCES_SUBNET_ID}",
        f"WORKERS_EC2_INSTANCES_TIME_BEFORE_DRAINING={app_settings.CLUSTERS_KEEPER_WORKERS_EC2_INSTANCES.WORKERS_EC2_INSTANCES_TIME_BEFORE_DRAINING}",
        f"WORKERS_EC2_INSTANCES_TIME_BEFORE_TERMINATION={app_settings.CLUSTERS_KEEPER_WORKERS_EC2_INSTANCES.WORKERS_EC2_INSTANCES_TIME_BEFORE_TERMINATION}",
    ]


def create_startup_script(
    app_settings: ApplicationSettings,
    *,
    ec2_boot_specific: EC2InstanceBootSpecific,
) -> str:
    assert app_settings.CLUSTERS_KEEPER_EC2_ACCESS  # nosec
    assert app_settings.CLUSTERS_KEEPER_WORKERS_EC2_INSTANCES  # nosec

    startup_commands = ec2_boot_specific.custom_boot_scripts.copy()
    return "\n".join(startup_commands)


def create_deploy_cluster_stack_script(
    app_settings: ApplicationSettings,
    *,
    cluster_machines_name_prefix: str,
    additional_custom_tags: EC2Tags,
) -> str:
    deploy_script: list[CommandStr] = []
    assert app_settings.CLUSTERS_KEEPER_PRIMARY_EC2_INSTANCES  # nosec
    if isinstance(
        app_settings.CLUSTERS_KEEPER_COMPUTATIONAL_BACKEND_DEFAULT_CLUSTER_AUTH,
        TLSAuthentication,
    ):
        # get the dask certificates
        download_certificates_commands = [
            f"mkdir --parents {_HOST_CERTIFICATES_BASE_PATH}",
            f'aws ssm get-parameter --name "{app_settings.CLUSTERS_KEEPER_PRIMARY_EC2_INSTANCES.PRIMARY_EC2_INSTANCES_SSM_TLS_DASK_CA}" --region us-east-1 --with-decryption --query "Parameter.Value" --output text > {_HOST_TLS_CA_FILE_PATH}',
            f'aws ssm get-parameter --name "{app_settings.CLUSTERS_KEEPER_PRIMARY_EC2_INSTANCES.PRIMARY_EC2_INSTANCES_SSM_TLS_DASK_CERT}" --region us-east-1 --with-decryption --query "Parameter.Value" --output text > {_HOST_TLS_CERT_FILE_PATH}',
            f'aws ssm get-parameter --name "{app_settings.CLUSTERS_KEEPER_PRIMARY_EC2_INSTANCES.PRIMARY_EC2_INSTANCES_SSM_TLS_DASK_KEY}" --region us-east-1 --with-decryption --query "Parameter.Value" --output text > {_HOST_TLS_KEY_FILE_PATH}',
        ]
        deploy_script.extend(download_certificates_commands)

    environment_variables = _prepare_environment_variables(
        app_settings,
        cluster_machines_name_prefix=cluster_machines_name_prefix,
        additional_custom_tags=additional_custom_tags,
    )

    deploy_script.extend(
        [
            # NOTE: https://stackoverflow.com/questions/41203492/solving-redis-warnings-on-overcommit-memory-and-transparent-huge-pages-for-ubunt
            "sysctl vm.overcommit_memory=1",
            f"echo '{_docker_compose_yml_base64_encoded()}' | base64 -d > {_HOST_DOCKER_COMPOSE_PATH}",
            f"echo '{_prometheus_yml_base64_encoded()}' | base64 -d > {_HOST_PROMETHEUS_PATH}",
            f"echo '{_prometheus_basic_auth_yml_base64_encoded(app_settings.CLUSTERS_KEEPER_PRIMARY_EC2_INSTANCES.PRIMARY_EC2_INSTANCES_PROMETHEUS_USERNAME, app_settings.CLUSTERS_KEEPER_PRIMARY_EC2_INSTANCES.PRIMARY_EC2_INSTANCES_PROMETHEUS_PASSWORD.get_secret_value())}' | base64 -d > {_HOST_PROMETHEUS_WEB_PATH}",
            # NOTE: --default-addr-pool is necessary in order to prevent conflicts with AWS node IPs
            f"docker swarm init --default-addr-pool {app_settings.CLUSTERS_KEEPER_PRIMARY_EC2_INSTANCES.PRIMARY_EC2_INSTANCES_DOCKER_DEFAULT_ADDRESS_POOL}",
            f"{' '.join(environment_variables)} docker stack deploy --with-registry-auth --compose-file={_HOST_DOCKER_COMPOSE_PATH} dask_stack",
        ]
    )
    return "\n".join(deploy_script)


def _convert_ec2_state_to_cluster_state(
    ec2_state: InstanceStateNameType,
) -> ClusterState:
    match ec2_state:
        case "pending":
            return ClusterState.STARTED
        case "running":
            return ClusterState.RUNNING
        case _:
            return ClusterState.STOPPED


def _create_eta(
    instance_launch_time: datetime.datetime,
    *,
    dask_scheduler_ready: bool,
    max_cluster_start_time: datetime.timedelta,
) -> datetime.timedelta:
    now = arrow.utcnow().datetime
    estimated_time_to_running = instance_launch_time + max_cluster_start_time - now
    if dask_scheduler_ready is True:
        estimated_time_to_running = datetime.timedelta(seconds=0)
    return estimated_time_to_running


def create_cluster_from_ec2_instance(
    instance: EC2InstanceData,
    user_id: UserID,
    wallet_id: WalletID | None,
    *,
    dask_scheduler_ready: bool,
    cluster_auth: InternalClusterAuthentication,
    max_cluster_start_time: datetime.timedelta,
) -> OnDemandCluster:
    return OnDemandCluster(
        endpoint=get_scheduler_url(instance),
        authentication=cluster_auth,
        state=_convert_ec2_state_to_cluster_state(instance.state),
        user_id=user_id,
        wallet_id=wallet_id,
        dask_scheduler_ready=dask_scheduler_ready,
        eta=_create_eta(
            instance.launch_time,
            dask_scheduler_ready=dask_scheduler_ready,
            max_cluster_start_time=max_cluster_start_time,
        ),
    )
