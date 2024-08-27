# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-statements

from pathlib import Path
from typing import Iterator

import pytest
import sqlalchemy as sa
from aiohttp.test_utils import TestClient
from models_library.folders import FolderID
from pytest_mock import MockerFixture
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.webserver_login import UserInfoDict
from pytest_simcore.helpers.webserver_parametrizations import (
    ExpectedResponse,
    standard_role_response,
)
from simcore_postgres_database.models.folders_never_used import (
    folders_never_used,
    folders_never_used_to_projects,
)
from simcore_service_webserver._meta import api_version_prefix
from simcore_service_webserver.db.models import UserRole
from simcore_service_webserver.projects.models import ProjectDict

# from .test_projects_crud_handlers__list_with_query_params import _assert_response_data


def standard_user_role() -> tuple[str, tuple[UserRole, ExpectedResponse]]:
    all_roles = standard_role_response()

    return (all_roles[0], [pytest.param(*all_roles[1][2], id="standard user role")])


@pytest.fixture
def mock_catalog_api_get_services_for_user_in_product(mocker: MockerFixture):
    mocker.patch(
        "simcore_service_webserver.projects._crud_api_read.get_services_for_user_in_product",
        spec=True,
        return_value=[],
    )


@pytest.fixture()
def setup_folders_db(
    postgres_db: sa.engine.Engine,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
) -> Iterator[FolderID]:
    with postgres_db.connect() as con:
        result = con.execute(
            folders_never_used.insert()
            .values(
                name="My Folder 1",
                description="My Folder Decription",
                product_name="osparc",
                created_by=logged_user["primary_gid"],
            )
            .returning(folders_never_used.c.id)
        )
        _folder_id = result.fetchone()[0]

        con.execute(
            folders_never_used_to_projects.insert().values(
                folder_id=_folder_id, project_uuid=user_project["uuid"]
            )
        )

        yield FolderID(_folder_id)

        con.execute(folders_never_used_to_projects.delete())
        con.execute(folders_never_used.delete())


@pytest.fixture
def app_environment(
    app_environment: EnvVarsDict, monkeypatch: pytest.MonkeyPatch
) -> EnvVarsDict:
    # disable the webserver folders plugin
    monkeypatch.setenv("WEBSERVER_FOLDERS", "0")
    return app_environment | {"WEBSERVER_FOLDERS": "0"}


@pytest.mark.parametrize(*standard_user_role())
async def test_list_projects_with_disabled_project_folders_plugin(
    client: TestClient,
    app_environment: EnvVarsDict,
    expected: ExpectedResponse,
    fake_project: ProjectDict,
    tests_data_dir: Path,
    osparc_product_name: str,
    project_db_cleaner,
    mock_catalog_api_get_services_for_user_in_product,
    setup_folders_db,
):
    """
    As the WEBSERVER_FOLDERS plugin is turned off, the project listing
    should behave the same way as before, and therefore list all the projects
    in the root directory, essentially ignoring the folders_to_projects table.
    """
    base_url = client.app.router["list_projects"].url_for()
    assert f"{base_url}" == f"/{api_version_prefix}/projects"

    resp = await client.get(base_url)
    data = await resp.json()

    assert resp.status == 200
    assert data["_meta"]["total"] == 1
