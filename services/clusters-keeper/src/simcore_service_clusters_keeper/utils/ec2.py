from textwrap import dedent

from models_library.users import UserID
from models_library.wallets import WalletID

from .._meta import VERSION
from ..core.settings import ApplicationSettings


def get_ec2_tags(
    app_settings: ApplicationSettings, *, user_id: UserID, wallet_id: WalletID
) -> dict[str, str]:
    assert app_settings.CLUSTERS_KEEPER_EC2_INSTANCES  # nosec
    return {
        "io.simcore.clusters-keeper.version": f"{VERSION}",
        # NOTE: this one gets special treatment in AWS GUI and is applied to the name of the instance
        "Name": f"osparc-gateway-server-{app_settings.CLUSTERS_KEEPER_EC2_INSTANCES.EC2_INSTANCES_KEY_NAME}-user_id:{user_id}-wallet_id:{wallet_id}",
    }


def compose_user_data(bash_command: str) -> str:
    return dedent(
        f"""\
#!/bin/bash
echo "started user data bash script"
{bash_command}
echo "completed user data bash script"
"""
    )
