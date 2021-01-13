# pylint:disable=redefined-outer-name,unused-argument,too-many-arguments
import cgi
import json
import logging
import sys
import tempfile
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, Set

import aiofiles
import aiohttp
import aiopg
import aioredis
import pytest
from models_library.settings.redis import RedisConfig
from pytest_simcore.docker_registry import _pull_push_service
from pytest_simcore.helpers.utils_login import log_client_in
from servicelib.application import create_safe_application
from simcore_service_webserver.db import setup_db
from simcore_service_webserver.db_models import projects
from simcore_service_webserver.director import setup_director
from simcore_service_webserver.director_v2 import setup_director_v2
from simcore_service_webserver.login import setup_login
from simcore_service_webserver.projects import setup_projects
from simcore_service_webserver.resource_manager import setup_resource_manager
from simcore_service_webserver.rest import setup_rest
from simcore_service_webserver.security import setup_security
from simcore_service_webserver.security_roles import UserRole
from simcore_service_webserver.session import setup_session
from simcore_service_webserver.socketio import setup_socketio
from simcore_service_webserver.users import setup_users
from yarl import URL

log = logging.getLogger(__name__)

core_services = [
    "redis",
    "rabbit",
    "director",
    "director-v2",
    "postgres",
    "storage",
]
ops_services = ["minio", "adminer"]


CURRENT_DIR = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent

API_VERSION = "v0"
API_PREFIX = "/" + API_VERSION

# store only lowercase "v1", "v2", ... and "v1_compressed", "v2_compressed", ...
SUPPORTED_EXPORTER_VERSIONS = {"v1", "v1_compressed"}

KEYS_TO_IGNORE_FROM_COMPARISON = {"id", "uuid", "creation_date", "last_change_date"}


@pytest.fixture
async def db_engine(postgres_dsn: Dict) -> aiopg.sa.Engine:
    dsn = "postgresql://{user}:{password}@{host}:{port}/{database}".format(
        **postgres_dsn
    )
    return await aiopg.sa.create_engine(dsn)


@pytest.fixture(autouse=True)
def __drop_and_recreate_postgres__(database_from_template_before_each_function) -> None:
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
async def monkey_patch_aiohttp_request_url() -> None:
    old_request = aiohttp.ClientSession._request

    async def new_request(*args, **kwargs):
        assert len(args) == 3

        url = args[2]
        if isinstance(url, str):
            url = URL(url)

        if url.host == "director-v2":
            from pytest_simcore.helpers.utils_docker import get_service_published_port

            log.debug("MOCKING _request [before] url=%s", url)
            new_port = int(get_service_published_port("director-v2", 8000))
            url = url.with_host("172.17.0.1").with_port(new_port)
            log.debug("MOCKING _request [after] url=%s kwargs=%s", url, str(kwargs))

            args = args[0], args[1], url

        return await old_request(*args, **kwargs)

    aiohttp.ClientSession._request = new_request

    yield

    aiohttp.ClientSession._request = old_request


@pytest.fixture
def client(
    loop, aiohttp_client, app_config, postgres_with_template_db, mock_orphaned_services
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
    assert setup_resource_manager(app)

    yield loop.run_until_complete(
        aiohttp_client(
            app,
            server_kwargs={"port": cfg["main"]["port"], "host": cfg["main"]["host"]},
        )
    )


################ utils


async def login_user(client):
    """returns a logged in regular user"""
    return await log_client_in(client=client, user_data={"role": UserRole.USER.name})


def get_exported_projects() -> List[Path]:
    exporter_dir = CURRENT_DIR / ".." / "data" / "exporter"
    return [x for x in exporter_dir.glob("*.osparc")]


@pytest.fixture
async def mock_asyncio_subporcess(mocker):
    # TODO: The below bug is not allowing me to fully test,
    # mocking and waiting for an update
    # https://bugs.python.org/issue35621
    # this issue was patched in 3.8, no need
    if sys.version_info.major == 3 and sys.version_info.minor >= 8:
        raise RuntimeError(
            "Issue no longer present in this version of python, "
            "please remote this mock on python >= 3.8"
        )

    import subprocess

    async def create_subprocess_exec(*command, **extra_params):
        class MockResponse:
            def __init__(self, command, **kwargs):
                self.proc = subprocess.Popen(command, **extra_params)

            async def communicate(self):
                return self.proc.communicate()

            @property
            def returncode(self):
                return self.proc.returncode

        mock_response = MockResponse(command, **extra_params)

        return mock_response

    mocker.patch("asyncio.create_subprocess_exec", side_effect=create_subprocess_exec)


@pytest.fixture(scope="session")
def push_services_to_registry(
    docker_registry: str, node_meta_schema: Dict
) -> Dict[str, str]:
    """Adds a itisfoundation/sleeper in docker registry"""
    return _pull_push_service(
        "itisfoundation/sleeper", "2.0.2", docker_registry, node_meta_schema
    )


@contextmanager
def assemble_tmp_file_path(file_name: str) -> Path:
    # pylint: disable=protected-access
    # let us all thank codeclimate for this beautiful piece of code
    tmp_store_dir = Path("/") / f"tmp/{next(tempfile._get_candidate_names())}"
    tmp_store_dir.mkdir(parents=True, exist_ok=True)
    file_path = tmp_store_dir / file_name

    try:
        yield file_path
    finally:
        file_path.unlink()
        tmp_store_dir.rmdir()


async def query_project_from_db(
    db_engine: aiopg.sa.Engine, project_uuid: str
) -> Dict[str, Any]:
    async with db_engine.acquire() as conn:
        project_result = await conn.execute(
            projects.select().where(projects.c.uuid == project_uuid)
        )
        project = await project_result.first()
        assert project is not None
        return dict(project)


def replace_uuids_with_sequences(project: Dict[str, Any]) -> Dict[str, Any]:
    workbench = project["workbench"]
    ui = project["ui"]

    # extract keys in correct order based on node names to have an accurate comparison
    node_uuid_service_label_dict = {key: workbench[key]["label"] for key in workbench}
    # sort by node label name and store node key
    sorted_node_uuid_service_label_dict = [
        k
        for k, v in sorted(
            node_uuid_service_label_dict.items(), key=lambda item: item[1]
        )
    ]
    # map node key to a sequential value
    remapping_dict = {
        key: f"uuid_seq_{i}"
        for i, key in enumerate(sorted_node_uuid_service_label_dict + [project["uuid"]])
    }

    str_workbench = json.dumps(workbench)
    str_ui = json.dumps(ui)
    for search_key, replace_key in remapping_dict.items():
        str_workbench = str_workbench.replace(search_key, replace_key)
        str_ui = str_ui.replace(search_key, replace_key)

    project["workbench"] = json.loads(str_workbench)
    project["ui"] = json.loads(str_ui)

    return project


def dict_without_keys(dict_data: Dict[str, Any], keys: Set[str]) -> Dict[str, Any]:
    result = deepcopy(dict_data)
    for key in keys:
        result.pop(key, None)
    return result


################ end utils


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


@pytest.mark.parametrize("export_version", get_exported_projects())
async def test_import_export_import(
    client,
    push_services_to_registry,
    socketio_client,
    db_engine,
    redis_client,
    export_version,
    mock_asyncio_subporcess,
    simcore_services,
    monkey_patch_aiohttp_request_url,
):
    """Check that the full import -> export -> import cycle produces the same result in the DB"""

    _ = await login_user(client)
    export_file_name = export_version.name
    version_from_name = export_file_name.split("#")[0]

    assert_error = (
        f"The '{version_from_name}' version' is not present in the supported versions: "
        f"{SUPPORTED_EXPORTER_VERSIONS}. If it's a new version please remember to add it."
    )
    assert version_from_name in SUPPORTED_EXPORTER_VERSIONS, assert_error

    imported_project_uuid = await import_study_from_file(client, export_version)

    # export newly imported project
    url_export = client.app.router["export_project"].url_for(
        project_id=imported_project_uuid
    )
    assert url_export == URL(API_PREFIX + f"/projects/{imported_project_uuid}/export")
    async with await client.get(url_export, timeout=10) as export_response:
        assert export_response.status == 200, await export_response.text()

        content_disposition_header = export_response.headers["Content-Disposition"]
        file_to_download_name = cgi.parse_header(content_disposition_header)[1][
            "filename"
        ]
        assert file_to_download_name.endswith(".osparc")

        with assemble_tmp_file_path(file_to_download_name) as downloaded_file_path:
            async with aiofiles.open(downloaded_file_path, mode="wb") as f:
                await f.write(await export_response.read())
                log.info("output_path %s", downloaded_file_path)

            reimported_project_uuid = await import_study_from_file(
                client, downloaded_file_path
            )

    imported_project = await query_project_from_db(db_engine, imported_project_uuid)
    reimported_project = await query_project_from_db(db_engine, reimported_project_uuid)

    # uuids are changed each time the project is imported, need to normalize them
    normalized_imported_project = replace_uuids_with_sequences(imported_project)
    normalized_reimported_project = replace_uuids_with_sequences(reimported_project)

    assert dict_without_keys(
        normalized_imported_project, KEYS_TO_IGNORE_FROM_COMPARISON
    ) == dict_without_keys(
        normalized_reimported_project, KEYS_TO_IGNORE_FROM_COMPARISON
    )
