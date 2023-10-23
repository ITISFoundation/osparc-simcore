from textwrap import dedent
from typing import Final

from models_library.users import UserID
from models_library.wallets import WalletID

from .._meta import VERSION
from ..core.settings import ApplicationSettings
from ..models import EC2Tags

_APPLICATION_TAG_KEY: Final[str] = "io.simcore.clusters-keeper"
_APPLICATION_VERSION_TAG: Final[EC2Tags] = {
    f"{_APPLICATION_TAG_KEY}.version": f"{VERSION}"
}

HEARTBEAT_TAG_KEY: Final[str] = "last_heartbeat"
CLUSTER_NAME_PREFIX: Final[str] = "osparc-computational-cluster-"


def get_cluster_name(
    app_settings: ApplicationSettings,
    *,
    user_id: UserID,
    wallet_id: WalletID | None,
    is_manager: bool,
) -> str:
    return f"{CLUSTER_NAME_PREFIX}{'manager' if is_manager else 'worker'}-{app_settings.SWARM_STACK_NAME}-user_id:{user_id}-wallet_id:{wallet_id}"


def _minimal_identification_tag(app_settings: ApplicationSettings) -> EC2Tags:
    return {".".join([_APPLICATION_TAG_KEY, "deploy"]): app_settings.SWARM_STACK_NAME}


def creation_ec2_tags(
    app_settings: ApplicationSettings, *, user_id: UserID, wallet_id: WalletID | None
) -> EC2Tags:
    assert app_settings.CLUSTERS_KEEPER_EC2_INSTANCES  # nosec
    return (
        _minimal_identification_tag(app_settings)
        | _APPLICATION_VERSION_TAG
        | {
            # NOTE: this one gets special treatment in AWS GUI and is applied to the name of the instance
            "Name": get_cluster_name(
                app_settings, user_id=user_id, wallet_id=wallet_id, is_manager=True
            ),
            "user_id": f"{user_id}",
            "wallet_id": f"{wallet_id}",
        }
    )


def all_created_ec2_instances_filter(app_settings: ApplicationSettings) -> EC2Tags:
    return _minimal_identification_tag(app_settings)


def ec2_instances_for_user_wallet_filter(
    app_settings: ApplicationSettings, *, user_id: UserID, wallet_id: WalletID | None
) -> EC2Tags:
    return (
        _minimal_identification_tag(app_settings)
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
