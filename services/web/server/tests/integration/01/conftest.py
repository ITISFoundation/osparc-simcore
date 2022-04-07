# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import asyncio
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, Tuple
from uuid import UUID

import pytest
from aiohttp.test_utils import TestClient
from models_library.projects import ProjectID
from pytest_simcore.helpers.utils_dict import ConfigDict
from pytest_simcore.helpers.utils_environs import EnvVarsDict
from pytest_simcore.helpers.utils_login import UserInfoDict, log_client_in
from simcore_service_webserver._meta import API_VTAG
from simcore_service_webserver.application import create_application
from simcore_service_webserver.security_roles import UserRole
from yarl import URL

# store only lowercase "v1", "v2", etc...
SUPPORTED_EXPORTER_VERSIONS = {"v1", "v2"}


@pytest.fixture
def client(
    event_loop: asyncio.AbstractEventLoop,
    aiohttp_client: Callable,
    app_config: ConfigDict,
    postgres_db,
    disable_static_webserver: Callable,
    monkeypatch_setenv_from_app_config: Callable[[EnvVarsDict], Dict[str, Any]],
    # postgres_with_template_db: aiopg.sa.engine.Engine,
    # mock_orphaned_services: mock.Mock,
    # database_from_template_before_each_function: None,
    # redis_client,
) -> Iterator[TestClient]:

    monkeypatch_setenv_from_app_config(app_config)
    cfg = deepcopy(app_config)

    assert cfg["rest"]["version"] == API_VTAG
    assert cfg["rest"]["enabled"]

    cfg["projects"]["enabled"] = True
    cfg["director"]["enabled"] = True

    app = create_application()

    yield event_loop.run_until_complete(
        aiohttp_client(
            app,
            server_kwargs={"port": cfg["main"]["port"], "host": cfg["main"]["host"]},
        )
    )


@pytest.fixture(scope="session", params=["v1", "v2"])
def exporter_version(request) -> str:
    return request.param


@pytest.fixture
def exported_project_file(tests_data_dir: Path, exporter_version: str) -> Path:
    exporter_dir = tests_data_dir / "exporter"
    assert exporter_dir.exists()
    exported_files = {x for x in exporter_dir.glob("*.osparc")}

    for exported_file in exported_files:
        if exported_file.name.startswith(exporter_version):
            return exported_file

    raise FileNotFoundError(f"{exporter_version=} not found in {exported_files}")


@pytest.fixture
async def login_user_and_import_study(
    client: TestClient,
    exported_project_file: Path,
) -> Tuple[ProjectID, UserInfoDict]:

    user = await log_client_in(client=client, user_data={"role": UserRole.USER.name})

    export_file_name = exported_project_file.name
    version_from_name = export_file_name.split("#")[0]

    assert_error = (
        f"The '{version_from_name}' version' is not present in the supported versions: "
        f"{SUPPORTED_EXPORTER_VERSIONS}. If it's a new version please remember to add it."
    )
    assert version_from_name in SUPPORTED_EXPORTER_VERSIONS, assert_error

    url_import = client.app.router["import_project"].url_for()
    assert url_import == URL(f"/{API_VTAG}/projects:import")

    data = {"fileName": open(exported_project_file, mode="rb")}
    async with await client.post(url_import, data=data, timeout=10) as import_response:
        assert import_response.status == 200, await import_response.text()
        reply_data = await import_response.json()
        assert reply_data.get("data") is not None

    imported_project_uuid = reply_data["data"]["uuid"]

    return UUID(imported_project_uuid), user
