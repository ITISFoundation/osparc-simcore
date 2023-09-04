from models_library.clusters import SimpleAuthentication
from models_library.rpc_schemas_clusters_keeper.clusters import (
    ClusterState,
    ComputationalCluster,
)
from models_library.users import UserID
from models_library.wallets import WalletID
from pydantic import AnyUrl, SecretStr, parse_obj_as
from types_aiobotocore_ec2.literals import InstanceStateNameType

from ..core.settings import ApplicationSettings
from ..models import EC2InstanceData


def create_startup_script(app_settings: ApplicationSettings) -> str:
    return "\n".join(
        [
            "git clone --depth=1 https://github.com/ITISFoundation/osparc-simcore.git",
            "cd osparc-simcore/services/osparc-gateway-server",
            "make config",
            f"echo 'c.Authenticator.password = \"{app_settings.CLUSTERS_KEEPER_COMPUTATIONAL_BACKEND_GATEWAY_PASSWORD.get_secret_value()}\"' >> .osparc-dask-gateway-config.py",
            f"DOCKER_IMAGE_TAG={app_settings.CLUSTERS_KEEPER_COMPUTATIONAL_BACKEND_DOCKER_IMAGE_TAG} make up",
        ]
    )


def _convert_ec2_state_to_cluster_state(
    ec2_state: InstanceStateNameType,
) -> ClusterState:
    match ec2_state:
        case "pending":
            return ClusterState.STARTED  # type: ignore
        case "running":
            return ClusterState.RUNNING  # type: ignore
        case _:
            return ClusterState.STOPPED  # type: ignore


def create_cluster_from_ec2_instance(
    instance: EC2InstanceData,
    user_id: UserID,
    wallet_id: WalletID,
    gateway_password: SecretStr,
) -> ComputationalCluster:
    return ComputationalCluster(
        endpoint=parse_obj_as(AnyUrl, f"http://{instance.aws_public_ip}"),
        authentication=SimpleAuthentication(
            username=f"{user_id}", password=gateway_password
        ),
        state=_convert_ec2_state_to_cluster_state(instance.state),
        user_id=user_id,
        wallet_id=wallet_id,
    )
