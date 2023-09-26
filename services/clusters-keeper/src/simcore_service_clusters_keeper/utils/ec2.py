from textwrap import dedent
from typing import Final

from models_library.users import UserID
from models_library.wallets import WalletID

from .._meta import VERSION
from ..core.settings import ApplicationSettings
from ..models import EC2Tags

_APPLICATION_TAG_KEY_NAME: Final[str] = "io.simcore.clusters-keeper.version"
_DEFAULT_CLUSTERS_KEEPER_TAGS: Final[dict[str, str]] = {
    _APPLICATION_TAG_KEY_NAME: f"{VERSION}"
}

HEARTBEAT_TAG_KEY: Final[str] = "last_heartbeat"


def creation_ec2_tags(
    app_settings: ApplicationSettings, *, user_id: UserID, wallet_id: WalletID | None
) -> EC2Tags:
    assert app_settings.CLUSTERS_KEEPER_EC2_INSTANCES  # nosec
    return _DEFAULT_CLUSTERS_KEEPER_TAGS | {
        # NOTE: this one gets special treatment in AWS GUI and is applied to the name of the instance
        "Name": f"osparc-computational-cluster-manager-{app_settings.SWARM_STACK_NAME}-user_id:{user_id}-wallet_id:{wallet_id}",
        "user_id": f"{user_id}",
        "wallet_id": f"{wallet_id}",
    }


def all_created_ec2_instances_filter() -> EC2Tags:
    return _DEFAULT_CLUSTERS_KEEPER_TAGS


def ec2_instances_for_user_wallet_filter(
    user_id: UserID, wallet_id: WalletID | None
) -> EC2Tags:
    return (
        _DEFAULT_CLUSTERS_KEEPER_TAGS
        | {"user_id": f"{user_id}"}
        | {"wallet_id": f"{wallet_id}"}
    )


def compose_user_data(bash_command: str) -> str:
    return dedent(
        f"""\
#!/bin/bash
echo "started user data bash script"
{bash_command}
echo "completed user data bash script"
"""
    )
