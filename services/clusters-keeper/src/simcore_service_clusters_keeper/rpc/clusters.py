from fastapi import FastAPI
from models_library.users import UserID
from models_library.wallets import WalletID

from ..core.errors import Ec2InstanceNotFoundError
from ..models import ClusterGet, EC2InstanceData
from ..modules import clusters
from .rpc_router import RPCRouter

router = RPCRouter()


@router.expose()
async def get_or_create_cluster(
    app: FastAPI, *, user_id: UserID, wallet_id: WalletID
) -> ClusterGet:
    ec2_instance = None
    try:
        ec2_instance = await clusters.get_cluster(
            app, user_id=user_id, wallet_id=wallet_id
        )
    except Ec2InstanceNotFoundError:
        new_ec2_instances = await clusters.create_cluster(
            app, user_id=user_id, wallet_id=wallet_id
        )
        assert new_ec2_instances  # nosec
        assert len(new_ec2_instances) == 1  # nosec
        ec2_instance = new_ec2_instances[0]
    assert ec2_instance is not None  # nosec

    return ClusterGet.from_ec2_instance_data(ec2_instance, user_id, wallet_id)


@router.expose()
async def create_cluster(
    app: FastAPI, *, user_id: UserID, wallet_id: WalletID
) -> list[EC2InstanceData]:
    return await clusters.create_cluster(app, user_id=user_id, wallet_id=wallet_id)


@router.expose()
async def cluster_heartbeat(
    app: FastAPI, *, user_id: UserID, wallet_id: WalletID
) -> None:
    return await clusters.cluster_heartbeat(app, user_id=user_id, wallet_id=wallet_id)
