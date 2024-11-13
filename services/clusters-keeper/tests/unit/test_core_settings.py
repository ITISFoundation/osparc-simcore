# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import json
import random

import pytest
from aws_library.ec2 import EC2InstanceBootSpecific
from pydantic import ValidationError
from pytest_simcore.helpers.monkeypatch_envs import EnvVarsDict, setenvs_from_dict
from simcore_service_clusters_keeper.core.settings import ApplicationSettings
from types_aiobotocore_ec2.literals import InstanceTypeType


def test_settings(app_environment: EnvVarsDict):
    settings = ApplicationSettings.create_from_envs()
    assert settings.CLUSTERS_KEEPER_EC2_ACCESS
    assert settings.CLUSTERS_KEEPER_PRIMARY_EC2_INSTANCES
    assert settings.CLUSTERS_KEEPER_RABBITMQ
    assert settings.CLUSTERS_KEEPER_REDIS
    assert settings.CLUSTERS_KEEPER_WORKERS_EC2_INSTANCES


@pytest.mark.xfail(
    reason="disabling till pydantic2 migration is complete see https://github.com/ITISFoundation/osparc-simcore/pull/6705"
)
def test_empty_primary_ec2_instances_raises(
    app_environment: EnvVarsDict,
    monkeypatch: pytest.MonkeyPatch,
):
    setenvs_from_dict(
        monkeypatch, {"PRIMARY_EC2_INSTANCES_ALLOWED_TYPES": json.dumps({})}
    )
    with pytest.raises(ValidationError, match="Only one exact value"):
        ApplicationSettings.create_from_envs()


@pytest.mark.xfail(
    reason="disabling till pydantic2 migration is complete see https://github.com/ITISFoundation/osparc-simcore/pull/6705"
)
def test_multiple_primary_ec2_instances_raises(
    app_environment: EnvVarsDict,
    monkeypatch: pytest.MonkeyPatch,
    ec2_instances: list[InstanceTypeType],
):
    setenvs_from_dict(
        monkeypatch,
        {
            "PRIMARY_EC2_INSTANCES_ALLOWED_TYPES": json.dumps(
                {
                    ec2_type_name: random.choice(  # noqa: S311
                        EC2InstanceBootSpecific.model_config["json_schema_extra"][
                            "examples"
                        ]
                    )
                    for ec2_type_name in ec2_instances
                }
            )
        },
    )
    with pytest.raises(ValidationError, match="Only one exact value"):
        ApplicationSettings.create_from_envs()


@pytest.mark.xfail(
    reason="disabling till pydantic2 migration is complete see https://github.com/ITISFoundation/osparc-simcore/pull/6705"
)
@pytest.mark.parametrize(
    "invalid_tag",
    [
        {".": "single dot is invalid"},
        {"..": "single 2 dots is invalid"},
        {"": "empty tag key"},
        {"/": "slash is invalid"},
        {" ": "space is invalid"},
    ],
    ids=str,
)
def test_invalid_primary_custom_tags_raises(
    app_environment: EnvVarsDict,
    monkeypatch: pytest.MonkeyPatch,
    invalid_tag: dict[str, str],
):
    setenvs_from_dict(
        monkeypatch,
        {"PRIMARY_EC2_INSTANCES_CUSTOM_TAGS": json.dumps(invalid_tag)},
    )
    with pytest.raises(ValidationError):
        ApplicationSettings.create_from_envs()


@pytest.mark.parametrize(
    "valid_tag",
    [
        {"...": "3 dots is valid"},
        {"..fdkjdlk..dsflkjsd=-lkjfie@": ""},
        {"abcdef-lsaj+-=._:@": "values are able to take almost anything"},
    ],
    ids=str,
)
def test_valid_primary_custom_tags(
    app_environment: EnvVarsDict,
    monkeypatch: pytest.MonkeyPatch,
    valid_tag: dict[str, str],
):
    setenvs_from_dict(
        monkeypatch,
        {"PRIMARY_EC2_INSTANCES_CUSTOM_TAGS": json.dumps(valid_tag)},
    )
    ApplicationSettings.create_from_envs()
