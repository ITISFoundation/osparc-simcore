# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name

import asyncio
import logging
import sys
from collections.abc import AsyncIterable, Callable, Iterable
from copy import deepcopy
from email.message import EmailMessage
from pathlib import Path
from typing import Any
from zipfile import ZipFile

import aiofiles
import pytest
import redis.asyncio as aioredis
from aiohttp.test_utils import TestClient
from pytest_simcore.helpers.webserver_login import LoggedUser, UserInfoDict
from pytest_simcore.helpers.webserver_projects import (
    create_project,
    delete_all_projects,
    empty_project_data,
)
from servicelib.aiohttp.application import create_safe_application
from servicelib.rest_constants import X_PRODUCT_NAME_HEADER
from settings_library.rabbit import RabbitSettings
from simcore_service_webserver._meta import API_VTAG
from simcore_service_webserver.application import (
    setup_exporter,
    setup_login,
    setup_projects,
    setup_resource_manager,
    setup_rest,
    setup_security,
    setup_session,
    setup_socketio,
    setup_users,
)
from simcore_service_webserver.application_settings import setup_settings
from simcore_service_webserver.db.plugin import setup_db
from simcore_service_webserver.exporter import settings as exporter_settings
from simcore_service_webserver.exporter._formatter.archive import get_sds_archive_path
from simcore_service_webserver.projects.models import ProjectDict
from yarl import URL

pytest_simcore_core_services_selection = [
    "migration",
    "postgres",
    "redis",
    "rabbit",
]

_logger = logging.getLogger(__name__)


CURRENT_DIR = (
    (Path(sys.argv[0] if __name__ == "__main__" else __file__) / ".." / "..")
    .resolve()
    .parent
)

_MOCK_FRONTEND_NEW_TSR_FORMAT: dict[str, Any] = {
    "enabled": True,
    "tsr_target": {
        "r01": {"level": 4, "references": ""},
        "r02": {"level": 4, "references": ""},
        "r03": {"level": 4, "references": ""},
        "r04": {"level": 4, "references": ""},
        "r05": {"level": 4, "references": ""},
        "r06": {"level": 4, "references": ""},
        "r07": {"level": 4, "references": ""},
        "r08": {"level": 4, "references": ""},
        "r09": {"level": 4, "references": ""},
        "r10": {"level": 4, "references": ""},
        "r03b": {"references": ""},
        "r03c": {"references": ""},
        "r07b": {"references": ""},
        "r07c": {"references": ""},
        "r07d": {"references": ""},
        "r07e": {"references": ""},
        "r08b": {"references": ""},
        "r10b": {"references": ""},
    },
    "tsr_current": {
        "r01": {"level": 0, "references": ""},
        "r02": {"level": 0, "references": ""},
        "r03": {"level": 0, "references": ""},
        "r04": {"level": 0, "references": ""},
        "r05": {"level": 0, "references": ""},
        "r06": {"level": 0, "references": ""},
        "r07": {"level": 0, "references": ""},
        "r08": {"level": 0, "references": ""},
        "r09": {"level": 0, "references": ""},
        "r10": {"level": 0, "references": ""},
        "r03b": {"references": ""},
        "r03c": {"references": ""},
        "r07b": {"references": ""},
        "r07c": {"references": ""},
        "r07d": {"references": ""},
        "r07e": {"references": ""},
        "r08b": {"references": ""},
        "r10b": {"references": ""},
    },
}


async def _new_project(
    client: TestClient,
    user: UserInfoDict,
    product_name: str,
    project_template_file: Path,
) -> ProjectDict:
    """returns a project for the given user"""
    project_data = empty_project_data()
    project_data["quality"] = _MOCK_FRONTEND_NEW_TSR_FORMAT

    assert client.app
    return await create_project(
        client.app,
        project_data,
        user["id"],
        product_name=product_name,
        default_project_json=project_template_file,
    )


def _get_files_in_zip(zip_path: Path) -> set[str]:
    return {x.filename for x in ZipFile(zip_path).infolist()}


def _get_fake_template_projects() -> set[Path]:
    template_dir = CURRENT_DIR / "data"
    assert template_dir.exists()
    return set(template_dir.rglob("fake-template-projects*"))


@pytest.fixture(params=_get_fake_template_projects())
def template_path(request: pytest.FixtureRequest) -> Path:
    return request.param


@pytest.fixture
def product_name() -> str:
    return "osparc"


@pytest.fixture
def client(
    docker_swarm: None,
    event_loop: asyncio.AbstractEventLoop,
    aiohttp_client: Callable,
    app_config: dict,
    monkeypatch_setenv_from_app_config: Callable,
    redis_client: aioredis.Redis,
    rabbit_service: RabbitSettings,
    simcore_services_ready: None,
) -> Iterable[TestClient]:
    # test config & env vars ----------------------
    cfg = deepcopy(app_config)
    assert cfg["rest"]["version"] == API_VTAG
    assert cfg["rest"]["enabled"]

    cfg["projects"]["enabled"] = True
    cfg["exporter"]["enabled"] = True

    monkeypatch_setenv_from_app_config(cfg)

    # app setup ----------------------------------
    app = create_safe_application(cfg)

    # activates only security+restAPI sub-modules
    assert setup_settings(app)
    assert (
        exporter_settings.get_plugin_settings(app) is not None
    ), "Should capture defaults"

    setup_db(app)
    setup_session(app)
    setup_security(app)
    setup_rest(app)
    setup_login(app)
    setup_users(app)
    setup_projects(app)
    setup_exporter(app)  # <---- under test
    setup_socketio(app)
    setup_resource_manager(app)

    return event_loop.run_until_complete(
        aiohttp_client(
            app,
            server_kwargs={"port": cfg["main"]["port"], "host": cfg["main"]["host"]},
        )
    )


@pytest.fixture
async def user(client: TestClient) -> AsyncIterable[UserInfoDict]:
    async with LoggedUser(client=client) as user_info_dict:
        yield user_info_dict


@pytest.fixture
async def project(
    client: TestClient, template_path: Path, user: UserInfoDict, product_name: str
) -> AsyncIterable[ProjectDict]:
    project = await _new_project(
        client=client,
        user=user,
        product_name=product_name,
        project_template_file=template_path,
    )
    yield project
    await delete_all_projects(client.app)


@pytest.fixture
def dir_downloaded(tmp_path: Path) -> Path:
    new_dir = tmp_path / "downloaded"
    new_dir.mkdir(parents=True, exist_ok=True)
    assert new_dir.exists()
    return new_dir


@pytest.fixture
def dir_generated(tmp_path: Path) -> Path:
    new_dir = tmp_path / "generated"
    new_dir.mkdir(parents=True, exist_ok=True)
    assert new_dir.exists()
    return new_dir


async def test_export_project(
    client: TestClient,
    user: UserInfoDict,
    project: ProjectDict,
    product_name: str,
    dir_downloaded: Path,
    dir_generated: Path,
):
    project_id = project["uuid"]
    assert client.app

    url_export = client.app.router["export_project"].url_for(project_id=project_id)
    headers = {X_PRODUCT_NAME_HEADER: product_name}

    def _get_header_params(header):
        # cgi Deprecated since version 3.11, will be removed in version 3.13:
        # Used recommended alternative https://docs.python.org/3/library/cgi.html?highlight=parse_header#cgi.parse_header
        msg = EmailMessage()
        msg["content-type"] = header
        return msg["content-type"].params

    assert url_export == URL(f"/{API_VTAG}/projects/{project_id}:xport")
    async with await client.post(
        f"{url_export}", headers=headers, timeout=10
    ) as export_response:
        assert export_response.status == 200, await export_response.text()

        file_to_download_name = _get_header_params(
            export_response.headers["Content-Disposition"]
        )["filename"]
        assert file_to_download_name.endswith(".zip")

        download_file_path = dir_downloaded / file_to_download_name

        async with aiofiles.open(download_file_path, mode="wb") as f:
            await f.write(await export_response.read())
            _logger.info("downloaded archive at %s", download_file_path)

        generated_file_path = await get_sds_archive_path(
            app=client.app,
            tmp_dir=f"{dir_generated}",
            project_id=project_id,
            user_id=user["id"],
            product_name=product_name,
        )
        assert generated_file_path.exists()
        # cannot compare the contents since .xlsx contain some last change date

        assert _get_files_in_zip(generated_file_path) == _get_files_in_zip(
            download_file_path
        )
