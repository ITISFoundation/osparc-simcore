from fastapi import FastAPI
from models_library.users import UserID
from models_library.wallets import WalletID

from .core.settings import get_application_settings
from .modules.ec2 import get_ec2_client
from .utils.ec2 import get_ec2_tags


async def create_cluster(app: FastAPI, *, user_id: UserID, wallet_id: WalletID):
    ec2_client = get_ec2_client(app)
    app_settings = get_application_settings(app)
    assert app_settings.CLUSTERS_KEEPER_EC2_INSTANCES  # nosec
    ec2_instances = await ec2_client.start_aws_instance(
        app_settings.CLUSTERS_KEEPER_EC2_INSTANCES,
        instance_type="t2.micro",
        tags=get_ec2_tags(app_settings, user_id=user_id, wallet_id=wallet_id),
        startup_script="",
        number_of_instances=1,
    )
    return ec2_instances
