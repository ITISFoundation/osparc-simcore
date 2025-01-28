# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


import pytest
from pydantic import ValidationError
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from settings_library.ec2 import EC2Settings


def test_ec2_endpoint_defaults_to_null(monkeypatch: pytest.MonkeyPatch):
    setenvs_from_dict(
        monkeypatch,
        {
            "EC2_ACCESS_KEY_ID": "my_access_key_id",
            "EC2_REGION_NAME": "us-east-1",
            "EC2_SECRET_ACCESS_KEY": "my_secret_access_key",
        },
    )

    settings = EC2Settings.create_from_envs()
    assert settings.EC2_ENDPOINT is None


def test_ec2_endpoint_is_nullified(monkeypatch: pytest.MonkeyPatch):
    setenvs_from_dict(
        monkeypatch,
        {
            "EC2_ACCESS_KEY_ID": "my_access_key_id",
            "EC2_ENDPOINT": "null",
            "EC2_REGION_NAME": "us-east-1",
            "EC2_SECRET_ACCESS_KEY": "my_secret_access_key",
        },
    )

    settings = EC2Settings.create_from_envs()
    assert settings.EC2_ENDPOINT is None


def test_ec2_endpoint_invalid(monkeypatch: pytest.MonkeyPatch):
    setenvs_from_dict(
        monkeypatch,
        {
            "EC2_ACCESS_KEY_ID": "my_access_key_id",
            "EC2_ENDPOINT": "ftp://my_ec2_endpoint.com",
            "EC2_REGION_NAME": "us-east-1",
            "EC2_SECRET_ACCESS_KEY": "my_secret_access_key",
        },
    )

    with pytest.raises(ValidationError) as err_info:
        EC2Settings.create_from_envs()

    assert err_info.value.errors()
    err_info.value.errors()[0]["loc"] == ("EC2_ENDPOINT")
    err_info.value.errors()[0]["type"] == "url_scheme"


def test_ec2_endpoint_description():
    assert EC2Settings.model_fields["EC2_ACCESS_KEY_ID"].description is None
    assert EC2Settings.model_fields["EC2_ENDPOINT"].description is not None
