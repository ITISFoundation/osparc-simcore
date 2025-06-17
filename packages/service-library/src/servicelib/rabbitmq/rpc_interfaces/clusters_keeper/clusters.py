from typing import Final

from aiocache import cached  # type: ignore[import-untyped]
from models_library.api_schemas_clusters_keeper import CLUSTERS_KEEPER_RPC_NAMESPACE
from models_library.api_schemas_clusters_keeper.clusters import OnDemandCluster
from models_library.rabbitmq_basic_types import RPCMethodName
from models_library.users import UserID
from models_library.wallets import WalletID
from pydantic import TypeAdapter

from ....async_utils import run_sequentially_in_context
from ..._client_rpc import RabbitMQRPCClient
from ..._constants import RPC_REMOTE_METHOD_TIMEOUT_S

_TTL_CACHE_ON_CLUSTERS_S: Final[int] = 5

_GET_OR_CREATE_CLUSTER_METHOD_NAME: Final[RPCMethodName] = TypeAdapter(
    RPCMethodName
).validate_python("get_or_create_cluster")


@run_sequentially_in_context(target_args=["user_id", "wallet_id"])
@cached(
    ttl=_TTL_CACHE_ON_CLUSTERS_S,
    key_builder=lambda f, *_args, **kwargs: f"{f.__name__}_{kwargs['user_id']}_{kwargs['wallet_id']}",
)
async def get_or_create_cluster(
    client: RabbitMQRPCClient, *, user_id: UserID, wallet_id: WalletID | None
) -> OnDemandCluster:
    """**Remote method**

    Raises:
        RPCServerError -- if anything happens remotely
    """
    # NOTE: we tend to have burst of calls for the same cluster
    # the 1st decorator ensure all of these go 1 by 1
    # the 2nd decorator ensure that many calls in a short time will return quickly the same value
    on_demand_cluster: OnDemandCluster = await client.request(
        CLUSTERS_KEEPER_RPC_NAMESPACE,
        _GET_OR_CREATE_CLUSTER_METHOD_NAME,
        timeout_s=RPC_REMOTE_METHOD_TIMEOUT_S,
        user_id=user_id,
        wallet_id=wallet_id,
    )
    return on_demand_cluster
