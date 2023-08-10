import datetime
import logging
from dataclasses import asdict

from fastapi import FastAPI
from models_library.users import UserID
from models_library.wallets import WalletID
from servicelib.logging_utils import log_context

from .core.settings import get_application_settings
from .modules.ec2 import get_ec2_client
from .utils.ec2 import HEARTBEAT_TAG_KEY, creation_ec2_tags, ec2_tags_for_user

_logger = logging.getLogger(__name__)


async def create_cluster(app: FastAPI, *, user_id: UserID, wallet_id: WalletID):
    with log_context(
        _logger, logging.DEBUG, msg=f"create_cluster for {user_id=}, {wallet_id=}"
    ):
        ec2_client = get_ec2_client(app)
        app_settings = get_application_settings(app)
        assert app_settings.CLUSTERS_KEEPER_EC2_INSTANCES  # nosec
        ec2_instances = await ec2_client.start_aws_instance(
            app_settings.CLUSTERS_KEEPER_EC2_INSTANCES,
            instance_type="t2.micro",
            tags=creation_ec2_tags(app_settings, user_id=user_id, wallet_id=wallet_id),
            startup_script="",
            number_of_instances=1,
        )
    return [asdict(i) for i in ec2_instances]


async def cluster_heartbeat(
    app: FastAPI,
    *,
    user_id: UserID,
) -> None:
    with log_context(_logger, logging.DEBUG, msg=f"cluster_heartbeat for {user_id=}"):
        ec2_client = get_ec2_client(app)
        app_settings = get_application_settings(app)
        assert app_settings.CLUSTERS_KEEPER_EC2_INSTANCES  # nosec
        if instances := await ec2_client.get_instances(
            app_settings.CLUSTERS_KEEPER_EC2_INSTANCES, tags=ec2_tags_for_user(user_id)
        ):
            await ec2_client.set_instances_tags(
                instances,
                tags={
                    HEARTBEAT_TAG_KEY: f"{datetime.datetime.now(datetime.timezone.utc)}"
                },
            )
