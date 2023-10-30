from models_library.api_schemas_clusters_keeper import CLUSTERS_KEEPER_RPC_NAMESPACE
from models_library.api_schemas_clusters_keeper.clusters import OnDemandCluster
from models_library.rabbitmq_basic_types import RPCMethodName
from models_library.users import UserID
from models_library.wallets import WalletID

from ....rabbitmq import RabbitMQRPCClient


async def get_or_create_cluster(
    client: RabbitMQRPCClient, *, user_id: UserID, wallet_id: WalletID | None
) -> OnDemandCluster:
    on_demand_cluster: OnDemandCluster = await client.request(
        CLUSTERS_KEEPER_RPC_NAMESPACE,
        RPCMethodName("get_or_create_cluster"),
        timeout_s=300,
        user_id=user_id,
        wallet_id=wallet_id,
    )
    return on_demand_cluster
