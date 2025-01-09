import datetime

from aws_library.ec2 import EC2InstanceData
from aws_library.ec2._errors import EC2InstanceNotFoundError
from fastapi import FastAPI
from models_library.api_schemas_clusters_keeper.clusters import OnDemandCluster
from models_library.users import UserID
from models_library.wallets import WalletID
from servicelib.rabbitmq import RPCRouter
from servicelib.redis._decorators import exclusive

from ..core.settings import get_application_settings
from ..modules import clusters
from ..modules.dask import ping_scheduler
from ..modules.redis import get_redis_client
from ..utils.clusters import create_cluster_from_ec2_instance
from ..utils.dask import get_scheduler_auth, get_scheduler_url

router = RPCRouter()


@router.expose()
async def get_or_create_cluster(
    app: FastAPI, *, user_id: UserID, wallet_id: WalletID | None
) -> OnDemandCluster:
    """Get or create cluster for user_id and wallet_id
    This function will create a new instance on AWS if needed or return the already running one.
    It will also check that the underlying computational backend is up and running.
    Calling several time will always return the same cluster.
    """
    ec2_instance: EC2InstanceData | None = None
    redis = get_redis_client(app)
    dask_scheduler_ready = False
    cluster_auth = get_scheduler_auth(app)

    @exclusive(
        redis,
        lock_key=f"get_or_create_cluster-{user_id=}-{wallet_id=}",
        blocking=True,
        blocking_timeout=datetime.timedelta(seconds=10),
    )
    async def _locked_get_or_create_cluster() -> None:
        try:
            ec2_instance = await clusters.get_cluster(
                app, user_id=user_id, wallet_id=wallet_id
            )
        except EC2InstanceNotFoundError:
            new_ec2_instances = await clusters.create_cluster(
                app, user_id=user_id, wallet_id=wallet_id
            )
            assert new_ec2_instances  # nosec
            assert len(new_ec2_instances) == 1  # nosec
            ec2_instance = new_ec2_instances[0]

        dask_scheduler_ready = bool(
            ec2_instance.state == "running"
            and await ping_scheduler(get_scheduler_url(ec2_instance), cluster_auth)
        )
        if dask_scheduler_ready:
            await clusters.cluster_heartbeat(app, user_id=user_id, wallet_id=wallet_id)

    await _locked_get_or_create_cluster()

    assert ec2_instance is not None  # nosec
    app_settings = get_application_settings(app)
    assert app_settings.CLUSTERS_KEEPER_PRIMARY_EC2_INSTANCES  # nosec
    return create_cluster_from_ec2_instance(
        ec2_instance,
        user_id,
        wallet_id,
        dask_scheduler_ready=dask_scheduler_ready,
        cluster_auth=cluster_auth,
        max_cluster_start_time=app_settings.CLUSTERS_KEEPER_PRIMARY_EC2_INSTANCES.PRIMARY_EC2_INSTANCES_MAX_START_TIME,
    )
