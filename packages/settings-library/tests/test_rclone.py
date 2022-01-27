from typing import Set

from settings_library.rclone import S3Provider, RCloneSettings
from _pytest.monkeypatch import MonkeyPatch

import pytest


def _get_backend_type_options() -> Set[str]:
    return {x for x in dir(S3Provider) if not x.startswith("_")}


def test_supported_backends_did_not_change() -> None:
    _EXPECTED = {"AWS", "CEPH", "MINIO"}
    assert _EXPECTED == _get_backend_type_options(), (
        "Backend configuration change, please code support for "
        "it in volumes_resolver -> _get_s3_volume_driver_config. "
        "When done, adjust above list."
    )


@pytest.mark.parametrize(
    "endpoint, is_secure",
    [
        ("localhost", False),
        ("s3_aws", True),
        ("https://ceph.home", True),
        ("http://local.dev", False),
    ],
)
def test_expected_endpoint(
    endpoint: str, is_secure: bool, monkeypatch: MonkeyPatch
) -> None:
    monkeypatch.setenv("S3_PROVIDER", "MINIO")
    monkeypatch.setenv("S3_ENDPOINT", endpoint)
    monkeypatch.setenv("S3_SECURE", "true" if is_secure else "false")

    r_clone_settings = RCloneSettings.create_from_envs()

    protocol = "https" if is_secure else "http"
    assert r_clone_settings.endpoint_url.startswith(f"{protocol}://")
    assert r_clone_settings.endpoint_url.endswith(endpoint)
