from textwrap import dedent
from typing import Final

from aws_library.ec2 import AWSTagKey, AWSTagValue, EC2Tags
from models_library.users import UserID
from models_library.wallets import WalletID
from pydantic import TypeAdapter

from .._meta import VERSION
from ..constants import (
    MANAGER_ROLE_TAG_VALUE,
    ROLE_TAG_KEY,
    USER_ID_TAG_KEY,
    WALLET_ID_TAG_KEY,
)
from ..core.settings import ApplicationSettings

_APPLICATION_TAG_KEY: Final[str] = "io.simcore.clusters-keeper"
_APPLICATION_VERSION_TAG: Final[EC2Tags] = TypeAdapter(EC2Tags).validate_python(
    {f"{_APPLICATION_TAG_KEY}.version": f"{VERSION}"}
)

HEARTBEAT_TAG_KEY: Final[AWSTagKey] = TypeAdapter(AWSTagKey).validate_python(
    "last_heartbeat"
)
CLUSTER_NAME_PREFIX: Final[str] = "osparc-computational-cluster-"


def get_cluster_name(
    app_settings: ApplicationSettings,
    *,
    user_id: UserID,
    wallet_id: WalletID | None,
    is_manager: bool,
) -> str:
    return f"{app_settings.CLUSTERS_KEEPER_EC2_INSTANCES_PREFIX}{CLUSTER_NAME_PREFIX}{'manager' if is_manager else 'worker'}-{app_settings.SWARM_STACK_NAME}-user_id:{user_id}-wallet_id:{wallet_id}"


def _minimal_identification_tag(app_settings: ApplicationSettings) -> EC2Tags:
    return {
        AWSTagKey(".".join([_APPLICATION_TAG_KEY, "deploy",])): AWSTagValue(
            f"{app_settings.CLUSTERS_KEEPER_EC2_INSTANCES_PREFIX}{app_settings.SWARM_STACK_NAME}"
        )
    }


def creation_ec2_tags(
    app_settings: ApplicationSettings, *, user_id: UserID, wallet_id: WalletID | None
) -> EC2Tags:
    assert app_settings.CLUSTERS_KEEPER_PRIMARY_EC2_INSTANCES  # nosec
    return (
        _minimal_identification_tag(app_settings)
        | _APPLICATION_VERSION_TAG
        | {
            # NOTE: this one gets special treatment in AWS GUI and is applied to the name of the instance
            AWSTagKey("Name"): AWSTagValue(
                get_cluster_name(
                    app_settings, user_id=user_id, wallet_id=wallet_id, is_manager=True
                )
            ),
            USER_ID_TAG_KEY: AWSTagValue(f"{user_id}"),
            WALLET_ID_TAG_KEY: AWSTagValue(f"{wallet_id}"),
            ROLE_TAG_KEY: MANAGER_ROLE_TAG_VALUE,
        }
        | app_settings.CLUSTERS_KEEPER_PRIMARY_EC2_INSTANCES.PRIMARY_EC2_INSTANCES_CUSTOM_TAGS
    )


def all_created_ec2_instances_filter(app_settings: ApplicationSettings) -> EC2Tags:
    return _minimal_identification_tag(app_settings)


def ec2_instances_for_user_wallet_filter(
    app_settings: ApplicationSettings, *, user_id: UserID, wallet_id: WalletID | None
) -> EC2Tags:
    return (
        _minimal_identification_tag(app_settings)
        | {USER_ID_TAG_KEY: AWSTagValue(f"{user_id}")}
        | {WALLET_ID_TAG_KEY: AWSTagValue(f"{wallet_id}")}
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


def wallet_id_from_instance_tags(tags: EC2Tags) -> WalletID | None:
    wallet_id_str = tags[WALLET_ID_TAG_KEY]
    if wallet_id_str == "None":
        return None
    return WalletID(wallet_id_str)


def user_id_from_instance_tags(tags: EC2Tags) -> UserID:
    return UserID(tags[USER_ID_TAG_KEY])
