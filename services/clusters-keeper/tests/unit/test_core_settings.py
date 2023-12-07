# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import json
import random

import pytest
from aws_library.ec2.models import EC2InstanceBootSpecific
from pydantic import ValidationError
from pytest_simcore.helpers.utils_envs import EnvVarsDict, setenvs_from_dict
from simcore_service_clusters_keeper.core.settings import ApplicationSettings
from types_aiobotocore_ec2.literals import InstanceTypeType


def test_settings(app_environment: EnvVarsDict):
    settings = ApplicationSettings.create_from_envs()
    assert settings.CLUSTERS_KEEPER_EC2_ACCESS
    assert settings.CLUSTERS_KEEPER_PRIMARY_EC2_INSTANCES
    assert settings.CLUSTERS_KEEPER_RABBITMQ
    assert settings.CLUSTERS_KEEPER_REDIS
    assert settings.CLUSTERS_KEEPER_WORKERS_EC2_INSTANCES


def test_empty_primary_ec2_instances_raises(
    app_environment: EnvVarsDict,
    monkeypatch: pytest.MonkeyPatch,
):
    setenvs_from_dict(
        monkeypatch, {"PRIMARY_EC2_INSTANCES_ALLOWED_TYPES": json.dumps({})}
    )
    with pytest.raises(ValidationError, match="Only one exact value"):
        ApplicationSettings.create_from_envs()


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
                        EC2InstanceBootSpecific.Config.schema_extra["examples"]
                    )
                    for ec2_type_name in ec2_instances
                }
            )
        },
    )
    with pytest.raises(ValidationError, match="Only one exact value"):
        ApplicationSettings.create_from_envs()
