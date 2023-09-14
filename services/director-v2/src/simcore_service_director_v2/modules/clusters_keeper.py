import datetime
import logging

from models_library.clusters import BaseCluster, ClusterTypeInModel
from models_library.rpc_schemas_clusters_keeper.clusters import (
    ClusterState,
    OnDemandCluster,
)
from models_library.users import UserID
from servicelib.rabbitmq import (
    RabbitMQRPCClient,
    RemoteMethodNotRegisteredError,
    RPCMethodName,
    RPCNamespace,
)

from ..core.errors import (
    ComputationalBackendOnDemandClustersKeeperNotReadyError,
    ComputationalBackendOnDemandNotReadyError,
)

_logger = logging.getLogger(__name__)

_TIME_FORMAT = "{:02d}:{:02d}"  # format for minutes:seconds


def _format_delta(delta: datetime.timedelta) -> str:
    return _TIME_FORMAT.format(delta.seconds // 60, delta.seconds % 60)


async def get_or_create_on_demand_cluster(
    user_id: UserID, rabbitmq_rpc_client: RabbitMQRPCClient
) -> BaseCluster:
    try:
        returned_cluster: OnDemandCluster = await rabbitmq_rpc_client.request(
            RPCNamespace("clusters-keeper"),
            RPCMethodName("get_or_create_cluster"),
            timeout_s=300,
            user_id=user_id,
            wallet_id=None,  # NOTE: --> MD this will need to be replaced by the real walletID
        )
        _logger.info("received cluster: %s", returned_cluster)
        if returned_cluster.state is not ClusterState.RUNNING:
            raise ComputationalBackendOnDemandNotReadyError(
                eta=_format_delta(returned_cluster.eta)
            )
        if not returned_cluster.gateway_ready:
            raise ComputationalBackendOnDemandNotReadyError(
                eta=_format_delta(returned_cluster.eta)
            )

        return BaseCluster(
            name=f"{user_id=}on-demand-cluster",
            type=ClusterTypeInModel.ON_DEMAND,
            owner=user_id,
            endpoint=returned_cluster.endpoint,
            authentication=returned_cluster.authentication,
        )
    except RemoteMethodNotRegisteredError as exc:
        # no clusters-keeper, that is not going to work!
        raise ComputationalBackendOnDemandClustersKeeperNotReadyError from exc
