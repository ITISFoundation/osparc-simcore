import datetime

from fastapi import FastAPI
from models_library.users import UserID
from models_library.wallets import WalletID

from ..core.errors import Ec2InstanceNotFoundError
from ..core.settings import get_application_settings
from ..models import EC2InstanceData
from ..utils.ec2 import (
    HEARTBEAT_TAG_KEY,
    all_created_ec2_instances_filter,
    creation_ec2_tags,
    ec2_instances_for_user_wallet_filter,
)
from .ec2 import get_ec2_client


def _create_startup_script() -> str:
    return "\n".join(
        [
            "git clone https://github.com/ITISFoundation/osparc-simcore.git",
            "cd osparc-simcore/services/osparc-gateway-server",
            "make up-latest",
        ]
    )


async def create_cluster(
    app: FastAPI, *, user_id: UserID, wallet_id: WalletID
) -> list[EC2InstanceData]:
    ec2_client = get_ec2_client(app)
    app_settings = get_application_settings(app)
    assert app_settings.CLUSTERS_KEEPER_EC2_INSTANCES  # nosec
    return await ec2_client.start_aws_instance(
        app_settings.CLUSTERS_KEEPER_EC2_INSTANCES,
        instance_type="t2.micro",
        tags=creation_ec2_tags(app_settings, user_id=user_id, wallet_id=wallet_id),
        startup_script=_create_startup_script(),
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


async def get_cluster(
    app: FastAPI, *, user_id: UserID, wallet_id: WalletID
) -> EC2InstanceData:
    app_settings = get_application_settings(app)
    assert app_settings.CLUSTERS_KEEPER_EC2_INSTANCES  # nosec
    if instances := await get_ec2_client(app).get_instances(
        app_settings.CLUSTERS_KEEPER_EC2_INSTANCES,
        tags=ec2_instances_for_user_wallet_filter(user_id, wallet_id),
    ):
        assert len(instances) == 1  # nosec
        return instances[0]
    raise Ec2InstanceNotFoundError


async def cluster_heartbeat(
    app: FastAPI, *, user_id: UserID, wallet_id: WalletID
) -> None:
    ec2_client = get_ec2_client(app)
    app_settings = get_application_settings(app)
    assert app_settings.CLUSTERS_KEEPER_EC2_INSTANCES  # nosec
    instance = await get_cluster(app, user_id=user_id, wallet_id=wallet_id)
    await ec2_client.set_instances_tags(
        [instance],
        tags={HEARTBEAT_TAG_KEY: f"{datetime.datetime.now(datetime.timezone.utc)}"},
    )


async def delete_clusters(app: FastAPI, *, instances: list[EC2InstanceData]) -> None:
    await get_ec2_client(app).terminate_instances(instances)
