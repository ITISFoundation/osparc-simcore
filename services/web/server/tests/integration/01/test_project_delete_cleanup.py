# pylint:disable=redefined-outer-name,unused-argument,too-many-arguments
import asyncio
import logging
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Set, Final
from unittest import mock
from uuid import UUID

import aioboto3
import aiopg
import aiopg.sa
import aioredis
import pytest
from aiohttp.test_utils import TestClient
from models_library.projects import ProjectID
from models_library.settings.redis import RedisConfig
from pytest_simcore.helpers.utils_login import log_client_in
from servicelib.aiohttp.application import create_safe_application
from simcore_service_webserver.application import (
    setup_director,
    setup_director_v2,
    setup_exporter,
    setup_login,
    setup_products,
    setup_projects,
    setup_resource_manager,
    setup_rest,
    setup_security,
    setup_session,
    setup_socketio,
    setup_storage,
    setup_users,
)
from simcore_service_webserver.catalog import setup_catalog
from simcore_service_webserver.db import setup_db
from simcore_service_webserver.scicrunch.submodule_setup import (
    setup_scicrunch_submodule,
)
from simcore_service_webserver.security_roles import UserRole
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

CURRENT_DIR = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent

DATA_DIR = CURRENT_DIR.parent.parent / "data"
assert DATA_DIR.exists(), "expected folder under tests/data"

API_VERSION = "v0"
API_PREFIX = "/" + API_VERSION

# store only lowercase "v1", "v2", etc...
SUPPORTED_EXPORTER_VERSIONS = {"v1", "v2"}

S3_DATA_REMOVAL_SECONDS: Final[int] = 2

# FIXTURES


@pytest.fixture(autouse=True)
def __drop_and_recreate_postgres__(
    database_from_template_before_each_function,
) -> Iterator[None]:
    yield


@pytest.fixture(autouse=True)
async def __delete_all_redis_keys__(redis_service: RedisConfig):
    client = await aioredis.create_redis_pool(redis_service.dsn, encoding="utf-8")
    await client.flushall()
    client.close()
    await client.wait_closed()

    yield
    # do nothing on teadown


@pytest.fixture
def client(
    loop: asyncio.AbstractEventLoop,
    aiohttp_client: Callable,
    app_config: Dict,
    postgres_with_template_db: aiopg.sa.engine.Engine,
    mock_orphaned_services: mock.Mock,
):

    cfg = deepcopy(app_config)

    assert cfg["rest"]["version"] == API_VERSION
    assert cfg["rest"]["enabled"]
    cfg["projects"]["enabled"] = True
    cfg["director"]["enabled"] = True

    # fake config
    app = create_safe_application(cfg)

    # activates only security+restAPI sub-modules
    setup_db(app)
    setup_session(app)
    setup_security(app)
    setup_rest(app)
    setup_login(app)
    setup_users(app)
    setup_socketio(app)
    setup_projects(app)
    setup_director(app)
    setup_director_v2(app)
    setup_exporter(app)
    setup_storage(app)
    setup_products(app)
    setup_catalog(app)
    setup_scicrunch_submodule(app)
    assert setup_resource_manager(app)

    yield loop.run_until_complete(
        aiohttp_client(
            app,
            server_kwargs={"port": cfg["main"]["port"], "host": cfg["main"]["host"]},
        )
    )


# UTILS


async def login_user(client):
    """returns a logged in regular user"""
    return await log_client_in(client=client, user_data={"role": UserRole.USER.name})


def get_exported_projects() -> List[Path]:
    # These files are generated from the front-end
    # when the formatter be finished
    exporter_dir = DATA_DIR / "exporter"
    assert exporter_dir.exists()
    exported_files = [x for x in exporter_dir.glob("*.osparc")]
    assert exported_files, "expected *.osparc files, none found"
    return exported_files


async def import_study_from_file(client, file_path: Path) -> str:
    url_import = client.app.router["import_project"].url_for()
    assert url_import == URL(API_PREFIX + "/projects:import")

    data = {"fileName": open(file_path, mode="rb")}
    async with await client.post(url_import, data=data, timeout=10) as import_response:
        assert import_response.status == 200, await import_response.text()
        reply_data = await import_response.json()
        assert reply_data.get("data") is not None

    imported_project_uuid = reply_data["data"]["uuid"]
    return imported_project_uuid


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


@pytest.mark.parametrize(
    "export_version", get_exported_projects(), ids=(lambda p: p.name)
)
async def test_s3_cleanup_after_removal(
    client: TestClient,
    aiopg_engine: aiopg.sa.engine.Engine,
    redis_client: aioredis.Redis,
    export_version: Path,
    docker_registry: str,
    simcore_services_ready: None,
    minio_config: Dict[str, Any],
):
    await login_user(client)
    export_file_name = export_version.name
    version_from_name = export_file_name.split("#")[0]

    assert_error = (
        f"The '{version_from_name}' version' is not present in the supported versions: "
        f"{SUPPORTED_EXPORTER_VERSIONS}. If it's a new version please remember to add it."
    )
    assert version_from_name in SUPPORTED_EXPORTER_VERSIONS, assert_error

    imported_project_uuid = await import_study_from_file(client, export_version)

    async def _files_in_s3() -> Set[str]:
        return await _fetch_stored_files(
            minio_config=minio_config, project_id=UUID(imported_project_uuid)
        )

    # files should be present in S3 after import
    assert len(await _files_in_s3()) > 0

    url_delete = client.app.router["delete_project"].url_for(
        project_id=imported_project_uuid
    )
    assert url_delete == URL(API_PREFIX + f"/projects/{imported_project_uuid}")
    async with await client.delete(f"{url_delete}", timeout=10) as export_response:
        assert export_response.status == 204, await export_response.text()

    # give it some time to make sure data was removed
    await asyncio.sleep(S3_DATA_REMOVAL_SECONDS)

    # files from S3 should have been removed
    assert await _files_in_s3() == set()
