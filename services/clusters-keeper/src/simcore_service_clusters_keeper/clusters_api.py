import datetime
import logging

from fastapi import FastAPI
from models_library.users import UserID
from models_library.wallets import WalletID
from servicelib.logging_utils import log_context
from simcore_service_clusters_keeper.core.errors import Ec2InstanceNotFoundError

from .core.settings import get_application_settings
from .models import EC2InstanceData
from .modules.ec2 import get_ec2_client
from .utils.ec2 import (
    HEARTBEAT_TAG_KEY,
    all_created_ec2_instances_filter,
    creation_ec2_tags,
    ec2_instances_for_user_filter,
)

_logger = logging.getLogger(__name__)


async def create_cluster(app: FastAPI, *, user_id: UserID, wallet_id: WalletID):
    with log_context(
        _logger, logging.INFO, msg=f"create_cluster for {user_id=}, {wallet_id=}"
    ):
        ec2_client = get_ec2_client(app)
        app_settings = get_application_settings(app)
        assert app_settings.CLUSTERS_KEEPER_EC2_INSTANCES  # nosec
        return await ec2_client.start_aws_instance(
            app_settings.CLUSTERS_KEEPER_EC2_INSTANCES,
            instance_type="t2.micro",
            tags=creation_ec2_tags(app_settings, user_id=user_id, wallet_id=wallet_id),
            startup_script="",
            number_of_instances=1,
        )


async def get_all_clusters(app: FastAPI) -> list[EC2InstanceData]:
    app_settings = get_application_settings(app)
    assert app_settings.CLUSTERS_KEEPER_EC2_INSTANCES  # nosec
    return await get_ec2_client(app).get_instances(
        app_settings.CLUSTERS_KEEPER_EC2_INSTANCES,
        tags=all_created_ec2_instances_filter(),
        state_names=["running"],
    )


async def get_clusters_for_user(
    app: FastAPI, *, user_id: UserID
) -> list[EC2InstanceData]:
    app_settings = get_application_settings(app)
    assert app_settings.CLUSTERS_KEEPER_EC2_INSTANCES  # nosec
    return await get_ec2_client(app).get_instances(
        app_settings.CLUSTERS_KEEPER_EC2_INSTANCES,
        tags=ec2_instances_for_user_filter(user_id),
        state_names=["running"],
    )


async def cluster_heartbeat(
    app: FastAPI,
    *,
    user_id: UserID,
) -> None:
    with log_context(_logger, logging.DEBUG, msg=f"cluster_heartbeat for {user_id=}"):
        ec2_client = get_ec2_client(app)
        app_settings = get_application_settings(app)
        assert app_settings.CLUSTERS_KEEPER_EC2_INSTANCES  # nosec
        if instances := await get_clusters_for_user(app, user_id=user_id):
            await ec2_client.set_instances_tags(
                instances,
                tags={
                    HEARTBEAT_TAG_KEY: f"{datetime.datetime.now(datetime.timezone.utc)}"
                },
            )
        else:
            raise Ec2InstanceNotFoundError


async def delete_clusters(app: FastAPI, *, instances: list[EC2InstanceData]) -> None:
    with log_context(
        _logger, logging.INFO, msg=f"delete clusters {[i.id for i in instances]}"
    ):
        await get_ec2_client(app).terminate_instances(instances)
