# pylint: disable=redefined-outer-name

import pytest
from settings_library.r_clone import RCloneSettings, S3Provider
from settings_library.utils_r_clone import (
    _COMMON_SETTINGS_OPTIONS,
    get_r_clone_config,
    resolve_provider,
)


@pytest.fixture(params=list(S3Provider))
def r_clone_settings(request, monkeypatch) -> RCloneSettings:
    monkeypatch.setenv("R_CLONE_PROVIDER", request.param)
    monkeypatch.setenv("S3_ENDPOINT", "endpoint")
    monkeypatch.setenv("S3_ACCESS_KEY", "access_key")
    monkeypatch.setenv("S3_SECRET_KEY", "secret_key")
    monkeypatch.setenv("S3_BUCKET_NAME", "bucket_name")
    monkeypatch.setenv("S3_SECURE", "false")
    return RCloneSettings()


def test_r_clone_config_template_replacement(r_clone_settings: RCloneSettings) -> None:
    r_clone_config = get_r_clone_config(r_clone_settings, s3_config_key="target-s3")
    print(r_clone_config)

    assert "{endpoint}" not in r_clone_config
    assert "{access_key}" not in r_clone_config
    assert "{secret_key}" not in r_clone_config

    for key in _COMMON_SETTINGS_OPTIONS:
        assert key in r_clone_config


@pytest.mark.parametrize(
    "s3_provider, expected",
    [
        (S3Provider.AWS, "AWS"),
        (S3Provider.CEPH, "Ceph"),
        (S3Provider.MINIO, "Minio"),
    ],
)
def test_resolve_provider(s3_provider: S3Provider, expected: str) -> None:
    assert resolve_provider(s3_provider) == expected
