from fastapi import FastAPI
from models_library.users import UserID
from models_library.wallets import WalletID
from simcore_service_clusters_keeper.core.settings import get_application_settings

from ..core.errors import Ec2InstanceNotFoundError
from ..models import ClusterGet, EC2InstanceData
from ..modules import clusters
from ..modules.dask import ping_gateway
from .rpc_router import RPCRouter

router = RPCRouter()


@router.expose()
async def get_or_create_cluster(
    app: FastAPI, *, user_id: UserID, wallet_id: WalletID
) -> ClusterGet:
    """Get or create cluster for user_id and wallet_id
    This function will create a new instance on AWS if needed or return the already running one.
    It will also check that the underlying computational backend is up and running.
    Calling several time will always return the same cluster.
    """
    ec2_instance: EC2InstanceData | None = None
    try:
        ec2_instance = await clusters.get_cluster(
            app, user_id=user_id, wallet_id=wallet_id
        )
        await clusters.cluster_heartbeat(app, user_id=user_id, wallet_id=wallet_id)
    except Ec2InstanceNotFoundError:
        new_ec2_instances = await clusters.create_cluster(
            app, user_id=user_id, wallet_id=wallet_id
        )
        assert new_ec2_instances  # nosec
        assert len(new_ec2_instances) == 1  # nosec
        ec2_instance = new_ec2_instances[0]
    assert ec2_instance is not None  # nosec
    app_settings = get_application_settings(app)
    cluster_get = ClusterGet.from_ec2_instance_data(
        ec2_instance,
        user_id,
        wallet_id,
        app_settings.CLUSTERS_KEEPER_COMPUTATIONAL_BACKEND_GATEWAY_PASSWORD,
    )

    if ec2_instance.state == "running":
        cluster_get.gateway_ready = await ping_gateway(
            ec2_instance,
            app_settings.CLUSTERS_KEEPER_COMPUTATIONAL_BACKEND_GATEWAY_PASSWORD,
        )

    return cluster_get
