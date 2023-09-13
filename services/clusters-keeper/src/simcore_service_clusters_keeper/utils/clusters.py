import datetime
from typing import Final

from models_library.clusters import SimpleAuthentication
from models_library.rpc_schemas_clusters_keeper.clusters import (
    ClusterState,
    OnDemandCluster,
)
from models_library.users import UserID
from models_library.wallets import WalletID
from pydantic import SecretStr
from types_aiobotocore_ec2.literals import InstanceStateNameType

from ..core.settings import ApplicationSettings
from ..models import EC2InstanceData
from .dask import get_gateway_url


def create_startup_script(app_settings: ApplicationSettings) -> str:
    return "\n".join(
        [
            "git clone --depth=1 https://github.com/ITISFoundation/osparc-simcore.git",
            "cd osparc-simcore/services/osparc-gateway-server",
            "make config",
            f"echo 'c.Authenticator.password = \"{app_settings.CLUSTERS_KEEPER_COMPUTATIONAL_BACKEND_GATEWAY_PASSWORD.get_secret_value()}\"' >> .osparc-dask-gateway-config.py",
            "make .env",
            "echo 'COMPUTATION_SIDECAR_NUM_NON_USABLE_CPUS=0' >> .env",
            f"DOCKER_IMAGE_TAG={app_settings.CLUSTERS_KEEPER_COMPUTATIONAL_BACKEND_DOCKER_IMAGE_TAG} make up",
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
_GATEWAY_READYNESS_MAX_TIME: Final[datetime.timedelta] = datetime.timedelta(minutes=3)


def _create_eta(
    instance_launch_time: datetime.datetime,
    *,
    gateway_ready: bool,
) -> datetime.timedelta:
    now = datetime.datetime.now(datetime.timezone.utc)
    estimated_time_to_running = (
        instance_launch_time
        + _EC2_INSTANCE_MAX_START_TIME
        + _GATEWAY_READYNESS_MAX_TIME
        - now
    )
    if gateway_ready is True:
        estimated_time_to_running = datetime.timedelta(seconds=0)
    return estimated_time_to_running


def create_cluster_from_ec2_instance(
    instance: EC2InstanceData,
    user_id: UserID,
    wallet_id: WalletID,
    gateway_password: SecretStr,
    *,
    gateway_ready: bool,
) -> OnDemandCluster:
    return OnDemandCluster(
        endpoint=get_gateway_url(instance),
        authentication=SimpleAuthentication(
            username=f"{user_id}", password=gateway_password
        ),
        state=_convert_ec2_state_to_cluster_state(instance.state),
        user_id=user_id,
        wallet_id=wallet_id,
        gateway_ready=gateway_ready,
        eta=_create_eta(instance.launch_time, gateway_ready=gateway_ready),
    )
