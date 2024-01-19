# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument

import pytest
from pytest import MonkeyPatch
from settings_library.s3 import S3Settings


@pytest.fixture
def base_env(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("S3_ACCESS_KEY", "mocked")
    monkeypatch.setenv("S3_SECRET_KEY", "mocked")
    monkeypatch.setenv("S3_BUCKET_NAME", "mocked")


@pytest.mark.parametrize(
    "endpoint, secure, expected",
    [
        ("osparc.io", "true", "https://osparc.io"),
        ("osparc.io", "false", "http://osparc.io"),
        ("https://osparc.io", "true", "https://osparc.io"),
        ("https://osparc.io", "false", "https://osparc.io"),
        ("http://osparc.io", "true", "http://osparc.io"),
        ("http://osparc.io", "false", "http://osparc.io"),
    ],
)
def test_regression(
    monkeypatch: MonkeyPatch, endpoint: str, secure: str, expected: str, base_env: None
) -> None:
    monkeypatch.setenv("S3_ENDPOINT", endpoint)
    monkeypatch.setenv("S3_SECURE", secure)

    s3_settings = S3Settings()
    assert expected == s3_settings.S3_ENDPOINT
