from fastapi import FastAPI
from models_library.users import UserID
from models_library.wallets import WalletID

from .. import clusters_api
from ..models import EC2InstanceData
from .rpc_router import RPCRouter

router = RPCRouter()


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
