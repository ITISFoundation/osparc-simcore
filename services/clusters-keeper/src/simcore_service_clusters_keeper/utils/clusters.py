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


def create_startup_script(app_settings: ApplicationSettings) -> str:
    return "\n".join(
        [
            f"echo '{docker_compose_yml_base64_encoded()}' | base64 -d > docker-compose.yml",
            "docker swarm init",
            f"DOCKER_IMAGE_TAG={app_settings.CLUSTERS_KEEPER_COMPUTATIONAL_BACKEND_DOCKER_IMAGE_TAG} docker stack deploy --with-registry-auth --compose-file=docker-compose.yml dask_stack",
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
    minutes=3
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
