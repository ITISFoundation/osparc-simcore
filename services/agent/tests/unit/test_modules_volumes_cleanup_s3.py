# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=too-many-locals

import hashlib
from pathlib import Path
from typing import Optional

import aioboto3
import pytest
from aiodocker.volumes import DockerVolume
from pydantic import HttpUrl
from pytest import LogCaptureFixture
from simcore_service_agent.core.settings import ApplicationSettings
from simcore_service_agent.modules.volumes_cleanup._s3 import (
    S3Provider,
    _get_dir_name,
    _get_s3_path,
    store_to_s3,
)

# UTILS


def _get_file_hashes_in_path(
    path_to_hash: Path, exclude_files: Optional[set[Path]] = None
) -> set[tuple[Path, str]]:
    def _hash_path(path: Path):
        sha256_hash = hashlib.sha256()
        with path.open("rb") as file:
            # Read and update hash string value in blocks of 4K
            for byte_block in iter(lambda: file.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    if path_to_hash.is_file():
        return {(path_to_hash.relative_to(path_to_hash), _hash_path(path_to_hash))}

    if exclude_files is None:
        exclude_files = set()

    return {
        (path.relative_to(path_to_hash), _hash_path(path))
        for path in path_to_hash.rglob("*")
        if path.is_file() and path.relative_to(path_to_hash) not in exclude_files
    }


async def _download_files_from_bucket(
    endpoint: str,
    access_key: str,
    secret_key: str,
    bucket_name: str,
    save_to: Path,
    swarm_stack_name: str,
    study_id: str,
    node_uuid: str,
    run_id: str,
) -> None:
    session = aioboto3.Session(
        aws_access_key_id=access_key, aws_secret_access_key=secret_key
    )
    async with session.resource("s3", endpoint_url=endpoint, use_ssl=False) as s_3:
        bucket = await s_3.Bucket(bucket_name)
        async for s3_object in bucket.objects.all():
            key_path = f"{swarm_stack_name}/{study_id}/{node_uuid}/{run_id}/"
            if s3_object.key.startswith(key_path):
                file_object = await s3_object.get()
                file_path: Path = save_to / s3_object.key.replace(key_path, "")
                file_path.parent.mkdir(parents=True, exist_ok=True)
                print(f"Saving file to {file_path}")
                file_content = await file_object["Body"].read()
                file_path.write_bytes(file_content)


def _create_data(folder: Path) -> None:
    for file in {  # pylint:disable=use-sequence-for-iteration
        ".hidden_do_not_remove",
        "key_values.json",
        "f1.txt",
        "f2.txt",
        "f3.txt",
        "d1/f1.txt",
        "d1/f2.txt",
        "d1/f3.txt",
        "d1/sd1/f1.txt",
        "d1/sd1/f2.txt",
        "d1/sd1/f3.txt",
    }:
        file_path = folder / file
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text("test")


# FIXTURES


@pytest.fixture
def save_to(tmp_path: Path) -> Path:
    return tmp_path / "save_to"


# TESTS


async def test_get_s3_path(
    unused_volume: DockerVolume,
    swarm_stack_name: str,
    study_id: str,
    node_uuid: str,
    run_id: str,
    bucket: str,
):
    volume_data = await unused_volume.show()
    assert _get_s3_path(bucket, volume_data["Labels"], unused_volume.name) == Path(
        f"/{bucket}/{swarm_stack_name}/{study_id}/{node_uuid}/{run_id}/{_get_dir_name(unused_volume.name)}"
    )


async def test_store_to_s3(
    unused_volume: DockerVolume,
    mocked_s3_server_url: HttpUrl,
    unused_volume_path: Path,
    save_to: Path,
    study_id: str,
    node_uuid: str,
    run_id: str,
    bucket: str,
    settings: ApplicationSettings,
):
    _create_data(unused_volume_path)
    dyv_volume = await unused_volume.show()

    # overwrite to test locally not against volume
    # root permissions are required to access this
    dyv_volume["Mountpoint"] = unused_volume_path

    await store_to_s3(
        volume_name=unused_volume.name,
        dyv_volume=dyv_volume,
        s3_access_key="xxx",
        s3_secret_key="xxx",
        s3_bucket=bucket,
        s3_endpoint=mocked_s3_server_url,
        s3_region="us-east-1",
        s3_provider=S3Provider.MINIO,
        s3_parallelism=3,
        s3_retries=1,
        exclude_files=settings.AGENT_VOLUMES_CLEANUP_EXCLUDE_FILES,
    )

    await _download_files_from_bucket(
        endpoint=mocked_s3_server_url,
        access_key="xxx",
        secret_key="xxx",
        bucket_name=bucket,
        save_to=save_to,
        swarm_stack_name=dyv_volume["Labels"]["swarm_stack_name"],
        study_id=study_id,
        node_uuid=node_uuid,
        run_id=run_id,
    )

    hashes_on_disk = _get_file_hashes_in_path(
        unused_volume_path, set(map(Path, settings.AGENT_VOLUMES_CLEANUP_EXCLUDE_FILES))
    )
    volume_path_without_source_dir = save_to / _get_dir_name(unused_volume.name)
    hashes_in_s3 = _get_file_hashes_in_path(volume_path_without_source_dir)
    assert len(hashes_on_disk) > 0
    assert len(hashes_in_s3) > 0
    assert hashes_on_disk == hashes_in_s3


@pytest.mark.parametrize("provider", [S3Provider.CEPH, S3Provider.MINIO])
async def test_regression_non_aws_providers(
    unused_volume: DockerVolume,
    mocked_s3_server_url: HttpUrl,
    unused_volume_path: Path,
    bucket: str,
    settings: ApplicationSettings,
    caplog_info_debug: LogCaptureFixture,
    provider: S3Provider,
):
    _create_data(unused_volume_path)
    dyv_volume = await unused_volume.show()

    # overwrite to test locally not against volume
    # root permissions are required to access this
    dyv_volume["Mountpoint"] = unused_volume_path

    await store_to_s3(
        volume_name=unused_volume.name,
        dyv_volume=dyv_volume,
        s3_access_key="xxx",
        s3_secret_key="xxx",
        s3_bucket=bucket,
        s3_endpoint=mocked_s3_server_url,
        s3_region="us-east-1",
        s3_provider=provider,
        s3_parallelism=3,
        s3_retries=1,
        exclude_files=settings.AGENT_VOLUMES_CLEANUP_EXCLUDE_FILES,
    )

    assert f'provider "{provider}" not known' not in caplog_info_debug.text
