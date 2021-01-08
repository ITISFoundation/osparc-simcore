# pylint:disable=redefined-outer-name,unused-argument,too-many-arguments
import logging
import sys
import re
from copy import deepcopy
from typing import Dict, List
from pathlib import Path

import aiopg
import aioredis
import pytest
from aioresponses import aioresponses
from yarl import URL
from models_library.projects_state import RunningState
from models_library.settings.redis import RedisConfig
from pytest_simcore.helpers.utils_login import log_client_in
from servicelib.application import create_safe_application
from simcore_service_webserver.db import setup_db
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

SUPPORTED_EXPORTER_VERSIONS = {"v1"}


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
async def director_v2_service_mock() -> aioresponses:
    """uses aioresponses to mock all calls of an aiohttpclient
    WARNING: any request done through the client will go through aioresponses. It is
    unfortunate but that means any valid request (like calling the test server) prefix must be set as passthrough.
    Other than that it seems to behave nicely
    """
    PASSTHROUGH_REQUESTS_PREFIXES = ["http://127.0.0.1", "ws://"]
    get_computation_pattern = re.compile(
        r"^http://[a-z\-_]*director-v2:[0-9]+/v2/computations/.*$"
    )
    delete_computation_pattern = get_computation_pattern
    # NOTE: GitHK I have to copy paste that fixture for some unclear reason for now.
    # I think this is due to some conflict between these non-pytest-simcore fixtures and the loop fixture being defined at different locations?? not sure..
    # anyway I think this should disappear once the garbage collector moves to its own micro-service
    with aioresponses(passthrough=PASSTHROUGH_REQUESTS_PREFIXES) as mock:
        mock.get(
            get_computation_pattern,
            status=202,
            payload={"state": str(RunningState.NOT_STARTED.value)},
            repeat=True,
        )
        mock.delete(delete_computation_pattern, status=204, repeat=True)
        yield mock


@pytest.fixture(autouse=True)
async def auto_mock_director_v2(
    director_v2_service_mock: aioresponses,
) -> aioresponses:
    return director_v2_service_mock


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


################ end utils


@pytest.mark.parametrize("export_version", get_exported_projects())
async def test_import_export_import(
    client,
    socketio_client,
    db_engine,
    redis_client,
    export_version,
    mock_asyncio_subporcess,
    simcore_services,
):
    """Check that the full import -> export -> import cycle produces the same result in the DB"""

    logged_user = await login_user(client)
    export_file_name = export_version.name
    version_from_name = export_file_name.split("#")[0]
    assert version_from_name in SUPPORTED_EXPORTER_VERSIONS

    url_import = client.app.router["import_project"].url_for()

    assert url_import == URL(API_PREFIX + "/projects/import")

    data = {"fileName": open(export_version, "rb")}

    async with await client.post(url_import, data=data, timeout=10) as import_response:
        assert import_response.status == 200, await import_response.text()
        reply_data = await import_response.json()

    imported_project_uuid = reply_data["uuid"]
    # TODO: fetch project and add it

    # TODO: this test is not finished and needs to be continued
    assert False