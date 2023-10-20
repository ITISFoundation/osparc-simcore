# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import pytest
from faker import Faker
from models_library.users import UserID
from models_library.wallets import WalletID
from simcore_service_clusters_keeper.core.settings import ApplicationSettings
from simcore_service_clusters_keeper.utils.ec2 import (
    _APPLICATION_TAG_KEY,
    all_created_ec2_instances_filter,
    compose_user_data,
    creation_ec2_tags,
)


@pytest.fixture
def user_id(faker: Faker) -> UserID:
    return faker.pyint(min_value=1)


@pytest.fixture
def wallet_id(faker: Faker) -> WalletID:
    return faker.pyint(min_value=1)


def test_creation_ec2_tags(
    mocked_aws_server_envs: None,
    disabled_rabbitmq: None,
    mocked_redis_server: None,
    app_settings: ApplicationSettings,
    user_id: UserID,
    wallet_id: WalletID,
):
    received_tags = creation_ec2_tags(
        app_settings, user_id=user_id, wallet_id=wallet_id
    )
    assert received_tags
    EXPECTED_TAG_KEY_NAMES = [_APPLICATION_TAG_KEY, "Name", "user_id", "wallet_id"]
    assert all(
        tag_key_name in received_tags for tag_key_name in EXPECTED_TAG_KEY_NAMES
    ), f"missing tag key names in {received_tags.keys()}, expected {EXPECTED_TAG_KEY_NAMES}"
    assert all(
        tag_key_name in EXPECTED_TAG_KEY_NAMES for tag_key_name in received_tags
    ), f"non expected tag key names in {received_tags.keys()}, expected {EXPECTED_TAG_KEY_NAMES}"


def test_all_created_ec2_instances_filter(
    app_settings: ApplicationSettings,
):
    received_filter = all_created_ec2_instances_filter(app_settings)
    assert len(received_filter) == 1
    assert _APPLICATION_TAG_KEY in received_filter


@pytest.fixture
def bash_command(faker: Faker) -> str:
    return faker.pystr()


def test_compose_user_data(bash_command: str):
    received_user_data = compose_user_data(bash_command)
    assert received_user_data
    assert received_user_data.startswith("#!/bin/bash\n")
    assert bash_command in received_user_data
