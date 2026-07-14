from textwrap import dedent

from aws_library.ec2 import AWSTagValue, EC2Tags
from models_library.products import ProductName
from models_library.users import UserID, UserIDAdapter
from models_library.wallets import WalletID, WalletIDAdapter
from pydantic import TypeAdapter

from ..constants import (
    APPLICATION_VERSION_TAG,
    CLUSTER_NAME_PREFIX,
    EC2_MINIMAL_APPLICATION_TAG_KEY,
    EC2_NAME_TAG_KEY,
    MANAGER_ROLE_TAG_VALUE,
    PRODUCT_NAME_TAG_KEY,
    ROLE_TAG_KEY,
    USER_ID_TAG_KEY,
    WALLET_ID_TAG_KEY,
)
from ..core.settings import ApplicationSettings


def get_cluster_name(
    app_settings: ApplicationSettings,
    *,
    user_id: UserID,
    wallet_id: WalletID | None,
    is_manager: bool,
) -> str:
    return (
        f"{app_settings.CLUSTERS_KEEPER_EC2_INSTANCES_PREFIX}{CLUSTER_NAME_PREFIX}"
        f"{'manager' if is_manager else 'worker'}-{app_settings.SWARM_STACK_NAME}"
        f"-user_id:{user_id}-wallet_id:{wallet_id}"
    )


def _minimal_identification_tag(app_settings: ApplicationSettings) -> EC2Tags:
    return {
        EC2_MINIMAL_APPLICATION_TAG_KEY: TypeAdapter(AWSTagValue).validate_python(
            f"{app_settings.CLUSTERS_KEEPER_EC2_INSTANCES_PREFIX}{app_settings.SWARM_STACK_NAME}"
        )
    }


def creation_ec2_tags(
    app_settings: ApplicationSettings,
    *,
    product_name: ProductName,
    user_id: UserID,
    wallet_id: WalletID | None,
) -> EC2Tags:
    assert app_settings.CLUSTERS_KEEPER_PRIMARY_EC2_INSTANCES  # nosec
    return (
        _minimal_identification_tag(app_settings)
        | APPLICATION_VERSION_TAG
        | {
            # NOTE: this one gets special treatment in AWS GUI and is applied to the name of the instance
            EC2_NAME_TAG_KEY: TypeAdapter(AWSTagValue).validate_python(
                get_cluster_name(app_settings, user_id=user_id, wallet_id=wallet_id, is_manager=True)
            ),
            PRODUCT_NAME_TAG_KEY: TypeAdapter(AWSTagValue).validate_python(f"{product_name}"),
            USER_ID_TAG_KEY: TypeAdapter(AWSTagValue).validate_python(f"{user_id}"),
            WALLET_ID_TAG_KEY: TypeAdapter(AWSTagValue).validate_python(f"{wallet_id}"),
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
        | {USER_ID_TAG_KEY: TypeAdapter(AWSTagValue).validate_python(f"{user_id}")}
        | {WALLET_ID_TAG_KEY: TypeAdapter(AWSTagValue).validate_python(f"{wallet_id}")}
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
    return WalletIDAdapter.validate_python(wallet_id_str)


def user_id_from_instance_tags(tags: EC2Tags) -> UserID:
    return UserIDAdapter.validate_python(tags[USER_ID_TAG_KEY])


def product_name_from_instance_tags(tags: EC2Tags) -> ProductName:
    return TypeAdapter(ProductName).validate_python(tags[PRODUCT_NAME_TAG_KEY])
