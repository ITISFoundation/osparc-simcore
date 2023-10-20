import base64
import datetime
import functools
from typing import Final

from models_library.clusters import NoAuthentication
from models_library.rpc_schemas_clusters_keeper.clusters import (
    ClusterState,
    OnDemandCluster,
)
from models_library.users import UserID
from models_library.wallets import WalletID
from types_aiobotocore_ec2.literals import InstanceStateNameType

from .._meta import PACKAGE_DATA_FOLDER
from ..core.settings import ApplicationSettings
from ..models import EC2InstanceData
from .dask import get_scheduler_url

_DOCKER_COMPOSE_FILE_NAME: Final[str] = "docker-compose.yml"


@functools.lru_cache
def docker_compose_yml_base64_encoded() -> str:
    file_path = PACKAGE_DATA_FOLDER / _DOCKER_COMPOSE_FILE_NAME
    assert file_path.exists()  # nosec
    with file_path.open("rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def create_startup_script(
    app_settings: ApplicationSettings, cluster_machines_name_prefix: str
) -> str:
    assert app_settings.CLUSTERS_KEEPER_EC2_ACCESS  # nosec
    assert app_settings.CLUSTERS_KEEPER_WORKERS_EC2_INSTANCES  # nosec
    environment_variables = [
        f"DOCKER_IMAGE_TAG={app_settings.CLUSTERS_KEEPER_COMPUTATIONAL_BACKEND_DOCKER_IMAGE_TAG}",
        f"EC2_ACCESS_KEY_ID={app_settings.CLUSTERS_KEEPER_EC2_ACCESS.CLUSTERS_KEEPER_EC2_ACCESS_KEY_ID}",
        f"EC2_ENDPOINT={app_settings.CLUSTERS_KEEPER_EC2_ACCESS.CLUSTERS_KEEPER_EC2_ENDPOINT}",
        f"EC2_INSTANCES_ALLOWED_TYPES={app_settings.CLUSTERS_KEEPER_WORKERS_EC2_INSTANCES.CLUSTERS_KEEPER_WORKERS_EC2_INSTANCES_ALLOWED_TYPES}",
        f"EC2_INSTANCES_AMI_ID={app_settings.CLUSTERS_KEEPER_WORKERS_EC2_INSTANCES.CLUSTERS_KEEPER_WORKERS_EC2_INSTANCES_AMI_ID}",
        f"EC2_INSTANCES_CUSTOM_BOOT_SCRIPTS={app_settings.CLUSTERS_KEEPER_WORKERS_EC2_INSTANCES.CLUSTERS_KEEPER_WORKERS_EC2_INSTANCES_CUSTOM_BOOT_SCRIPTS}",
        f"EC2_INSTANCES_KEY_NAME={app_settings.CLUSTERS_KEEPER_WORKERS_EC2_INSTANCES.CLUSTERS_KEEPER_WORKERS_EC2_INSTANCES_KEY_NAME}",
        f"EC2_INSTANCES_MAX_INSTANCES={app_settings.CLUSTERS_KEEPER_WORKERS_EC2_INSTANCES.CLUSTERS_KEEPER_WORKERS_EC2_INSTANCES_MAX_INSTANCES}",
        f"EC2_INSTANCES_NAME_PREFIX={cluster_machines_name_prefix}",
        f"EC2_INSTANCES_SECURITY_GROUP_IDS={app_settings.CLUSTERS_KEEPER_WORKERS_EC2_INSTANCES.CLUSTERS_KEEPER_WORKERS_EC2_INSTANCES_SECURITY_GROUP_IDS}",
        f"EC2_INSTANCES_SUBNET_ID={app_settings.CLUSTERS_KEEPER_WORKERS_EC2_INSTANCES.CLUSTERS_KEEPER_WORKERS_EC2_INSTANCES_SUBNET_ID}",
        f"EC2_REGION_NAME={app_settings.CLUSTERS_KEEPER_EC2_ACCESS.CLUSTERS_KEEPER_EC2_REGION_NAME}",
        f"EC2_SECRET_ACCESS_KEY={app_settings.CLUSTERS_KEEPER_EC2_ACCESS.CLUSTERS_KEEPER_EC2_SECRET_ACCESS_KEY}",
        f"LOG_LEVEL={app_settings.LOG_LEVEL}",
    ]

    return "\n".join(
        [
            f"echo '{docker_compose_yml_base64_encoded()}' | base64 -d > docker-compose.yml",
            "docker swarm init",
            f"{' '.join(environment_variables)} docker stack deploy --with-registry-auth --compose-file=docker-compose.yml dask_stack",
        ]
    )


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


_EC2_INSTANCE_MAX_START_TIME: Final[datetime.timedelta] = datetime.timedelta(minutes=3)
_DASK_SCHEDULER_READYNESS_MAX_TIME: Final[datetime.timedelta] = datetime.timedelta(
    minutes=1
)


def _create_eta(
    instance_launch_time: datetime.datetime,
    *,
    dask_scheduler_ready: bool,
) -> datetime.timedelta:
    now = datetime.datetime.now(datetime.timezone.utc)
    estimated_time_to_running = (
        instance_launch_time
        + _EC2_INSTANCE_MAX_START_TIME
        + _DASK_SCHEDULER_READYNESS_MAX_TIME
        - now
    )
    if dask_scheduler_ready is True:
        estimated_time_to_running = datetime.timedelta(seconds=0)
    return estimated_time_to_running


def create_cluster_from_ec2_instance(
    instance: EC2InstanceData,
    user_id: UserID,
    wallet_id: WalletID | None,
    *,
    dask_scheduler_ready: bool,
) -> OnDemandCluster:
    return OnDemandCluster(
        endpoint=get_scheduler_url(instance),
        authentication=NoAuthentication(),
        state=_convert_ec2_state_to_cluster_state(instance.state),
        user_id=user_id,
        wallet_id=wallet_id,
        dask_scheduler_ready=dask_scheduler_ready,
        eta=_create_eta(
            instance.launch_time, dask_scheduler_ready=dask_scheduler_ready
        ),
    )
