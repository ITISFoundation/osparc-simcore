# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import asyncio
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, AsyncIterable, Callable, Dict, Iterator, Tuple
from unittest import mock
from uuid import UUID

import aiopg
import aiopg.sa
import aioredis
import pytest
from aiohttp.test_utils import TestClient
from models_library.projects import ProjectID
from models_library.settings.redis import RedisConfig
from pytest_simcore.helpers.utils_environs import EnvVarsDict
from pytest_simcore.helpers.utils_login import AUserDict, log_client_in
from servicelib.aiohttp.application import create_safe_application
from simcore_service_webserver._meta import API_VTAG
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

# store only lowercase "v1", "v2", etc...
SUPPORTED_EXPORTER_VERSIONS = {"v1", "v2"}


@pytest.fixture
async def delete_all_redis_keys(redis_service: RedisConfig) -> AsyncIterable[None]:
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
    monkeypatch_setenv_from_app_config: Callable[[EnvVarsDict], Dict[str, Any]],
    postgres_with_template_db: aiopg.sa.engine.Engine,
    mock_orphaned_services: mock.Mock,
    database_from_template_before_each_function: None,
    delete_all_redis_keys: None,
) -> Iterator[TestClient]:

    monkeypatch_setenv_from_app_config(app_config)
    cfg = deepcopy(app_config)

    assert cfg["rest"]["version"] == API_VTAG
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


@pytest.fixture
async def login_user_and_import_study(
    client: TestClient,
    exported_project: Path,
) -> Tuple[ProjectID, AUserDict]:

    user = await log_client_in(client=client, user_data={"role": UserRole.USER.name})
    export_file_name = exported_project.name
    version_from_name = export_file_name.split("#")[0]

    assert_error = (
        f"The '{version_from_name}' version' is not present in the supported versions: "
        f"{SUPPORTED_EXPORTER_VERSIONS}. If it's a new version please remember to add it."
    )
    assert version_from_name in SUPPORTED_EXPORTER_VERSIONS, assert_error

    url_import = client.app.router["import_project"].url_for()
    assert url_import == URL(f"/{API_VTAG}/projects:import")

    data = {"fileName": open(exported_project, mode="rb")}
    async with await client.post(url_import, data=data, timeout=10) as import_response:
        assert import_response.status == 200, await import_response.text()
        reply_data = await import_response.json()
        assert reply_data.get("data") is not None

    imported_project_uuid = reply_data["data"]["uuid"]

    return UUID(imported_project_uuid), user


@pytest.fixture(scope="session", params=["v1", "v2"])
def exporter_version(request) -> str:
    return request.param


@pytest.fixture
def exported_project(exporter_version: str) -> Path:
    # These files are generated from the front-end
    # when the formatter be finished
    current_dir = (
        Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent
    )
    data_dir = current_dir.parent.parent / "data"
    assert data_dir.exists(), "expected folder under tests/data"
    exporter_dir = data_dir / "exporter"
    assert exporter_dir.exists()
    exported_files = {x for x in exporter_dir.glob("*.osparc")}

    for exported_file in exported_files:
        if exported_file.name.startswith(exporter_version):
            return exported_file

    raise FileNotFoundError(f"{exporter_version=} not found in {exported_files}")
