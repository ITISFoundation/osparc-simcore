from enum import auto

from fastapi import FastAPI
from models_library.clusters import ClusterAuthentication, SimpleAuthentication
from models_library.users import UserID
from models_library.utils.enums import StrAutoEnum
from models_library.wallets import WalletID
from pydantic import AnyUrl, BaseModel, SecretStr, parse_obj_as
from simcore_service_clusters_keeper.core.errors import Ec2InstanceNotFoundError
from types_aiobotocore_ec2.literals import InstanceStateNameType

from .. import clusters_api
from ..models import EC2InstanceData
from .rpc_router import RPCRouter

router = RPCRouter()


class ClusterState(StrAutoEnum):
    STARTED = auto()
    RUNNING = auto()
    TERMINATED = auto()


def _convert_ec2_state_to_cluster_state(
    ec2_state: InstanceStateNameType,
) -> ClusterState:
    match ec2_state:
        case "pending":
            return ClusterState.STARTED
        case "running":
            return ClusterState.RUNNING
        case _:
            return ClusterState.TERMINATED
    return ClusterState.TERMINATED


class ClusterGet(BaseModel):
    endpoint: AnyUrl
    authentication: ClusterAuthentication
    state: ClusterState
    user_id: UserID
    wallet_id: WalletID


@router.expose()
async def get_or_create_cluster(
    app: FastAPI, *, user_id: UserID, wallet_id: WalletID
) -> ClusterGet:
    ec2_instance = None
    try:
        ec2_instance = await clusters_api.get_cluster(
            app, user_id=user_id, wallet_id=wallet_id
        )
    except Ec2InstanceNotFoundError:
        new_ec2_instances = await clusters_api.create_cluster(
            app, user_id=user_id, wallet_id=wallet_id
        )
        assert new_ec2_instances  # nosec
        assert len(new_ec2_instances) == 1  # nosec
        ec2_instance = new_ec2_instances[0]
    assert ec2_instance is not None  # nosec

    return ClusterGet(
        endpoint=parse_obj_as(AnyUrl, f"http://{ec2_instance.aws_public_ip}"),
        authentication=SimpleAuthentication(
            username="bing", password=SecretStr("bing")
        ),
        state=_convert_ec2_state_to_cluster_state(ec2_instance.state),
        user_id=user_id,
        wallet_id=wallet_id,
    )


@router.expose()
async def create_cluster(
    app: FastAPI, *, user_id: UserID, wallet_id: WalletID
) -> list[EC2InstanceData]:
    return await clusters_api.create_cluster(app, user_id=user_id, wallet_id=wallet_id)


@router.expose()
async def cluster_heartbeat(
    app: FastAPI, *, user_id: UserID, wallet_id: WalletID
) -> None:
    return await clusters_api.cluster_heartbeat(
        app, user_id=user_id, wallet_id=wallet_id
    )
