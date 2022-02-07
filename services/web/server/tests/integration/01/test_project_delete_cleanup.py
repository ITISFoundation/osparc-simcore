# pylint:disable=redefined-outer-name,unused-argument,too-many-arguments
import logging
from typing import Any, Dict, Final, Set, Tuple

import aioboto3
import aiopg
import aiopg.sa
import aioredis
from aiohttp.test_utils import TestClient
from models_library.projects import ProjectID
from pytest_simcore.helpers.utils_login import AUserDict
from simcore_service_webserver._meta import API_VTAG
from tenacity._asyncio import AsyncRetrying
from tenacity.before_sleep import before_sleep_log
from tenacity.stop import stop_after_attempt
from tenacity.wait import wait_fixed
from yarl import URL

log = logging.getLogger(__name__)

pytest_simcore_core_services_selection = [
    "catalog",
    "dask-scheduler",
    "director-v2",
    "director",
    "migration",
    "postgres",
    "rabbit",
    "redis",
    "storage",
]
pytest_simcore_ops_services_selection = ["minio", "adminer"]

S3_DATA_REMOVAL_SECONDS: Final[int] = 2


# UTILS


async def _fetch_stored_files(
    minio_config: Dict[str, Any], project_id: ProjectID
) -> Set[str]:

    s3_config: Dict[str, str] = minio_config["client"]

    def _endpoint_url() -> str:
        protocol = "https" if s3_config["secure"] else "http"
        return f"{protocol}://{s3_config['endpoint']}"

    session = aioboto3.Session(
        aws_access_key_id=s3_config["access_key"],
        aws_secret_access_key=s3_config["secret_key"],
    )

    results: Set[str] = set()

    async with session.resource("s3", endpoint_url=_endpoint_url()) as s3:
        bucket = await s3.Bucket(minio_config["bucket_name"])
        async for s3_object in bucket.objects.all():
            key_path = f"{project_id}/"
            if s3_object.key.startswith(key_path):
                results.add(s3_object.key)

    return results


# TESTS


async def test_s3_cleanup_after_removal(
    client: TestClient,
    login_user_and_import_study: Tuple[ProjectID, AUserDict],
    minio_config: Dict[str, Any],
    aiopg_engine: aiopg.sa.engine.Engine,
    redis_client: aioredis.Redis,
    docker_registry: str,
    simcore_services_ready: None,
):
    imported_project_uuid, _ = login_user_and_import_study

    async def _files_in_s3() -> Set[str]:
        return await _fetch_stored_files(
            minio_config=minio_config, project_id=imported_project_uuid
        )

    # files should be present in S3 after import
    assert len(await _files_in_s3()) > 0

    url_delete = client.app.router["delete_project"].url_for(
        project_id=f"{imported_project_uuid}"
    )
    assert url_delete == URL(f"/{API_VTAG}/projects/{imported_project_uuid}")
    async with await client.delete(f"{url_delete}", timeout=10) as delete_response:
        assert delete_response.status == 204, await delete_response.text()

    # since it takes time for the task to properly remove the data
    # try a few times before giving up and failing the test
    async for attempt in AsyncRetrying(
        stop=stop_after_attempt(30),
        wait=wait_fixed(2),
        before_sleep=before_sleep_log(log, logging.WARNING),
    ):
        with attempt:
            assert await _files_in_s3() == set()
