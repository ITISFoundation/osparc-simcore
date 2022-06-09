from pydantic import ByteSize
from pytest import MonkeyPatch
from settings_library.r_clone import RCloneSettings


def test_overwrite_byte_size(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("R_CLONE_PROVIDER", "AWS")
    monkeypatch.setenv("S3_ENDPOINT", "endpoint")
    monkeypatch.setenv("S3_ACCESS_KEY", "access_key")
    monkeypatch.setenv("S3_SECRET_KEY", "secret_key")
    monkeypatch.setenv("S3_BUCKET_NAME", "bucket_name")

    # overwrite
    monkeypatch.setenv("R_CLONE_MEMORY_LIMIT", "2gib")
    monkeypatch.setenv("R_CLONE_MEMORY_RESERVATION", "200mib")

    r_clone_settings = RCloneSettings.create_from_envs()
    assert r_clone_settings.R_CLONE_MEMORY_LIMIT == ByteSize.validate("2gib")
    assert r_clone_settings.R_CLONE_MEMORY_RESERVATION == ByteSize.validate("200mib")
