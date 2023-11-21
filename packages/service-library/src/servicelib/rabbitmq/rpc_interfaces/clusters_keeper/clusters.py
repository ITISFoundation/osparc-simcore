from models_library.api_schemas_clusters_keeper import CLUSTERS_KEEPER_RPC_NAMESPACE
from models_library.api_schemas_clusters_keeper.clusters import OnDemandCluster
from models_library.rabbitmq_basic_types import RPCMethodName
from models_library.users import UserID
from models_library.wallets import WalletID

from ..._client_rpc import RabbitMQRPCClient
from ..._constants import RPC_REMOTE_METHOD_TIMEOUT_S


async def get_or_create_cluster(
    client: RabbitMQRPCClient, *, user_id: UserID, wallet_id: WalletID | None
) -> OnDemandCluster:
    """**Remote method**

    Raises:
        RPCServerError -- if anything happens remotely
    """
    on_demand_cluster: OnDemandCluster = await client.request(
        CLUSTERS_KEEPER_RPC_NAMESPACE,
        RPCMethodName("get_or_create_cluster"),
        timeout_s=RPC_REMOTE_METHOD_TIMEOUT_S,
        user_id=user_id,
        wallet_id=wallet_id,
    )
    return on_demand_cluster
