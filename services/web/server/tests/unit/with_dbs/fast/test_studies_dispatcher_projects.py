# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name


import logging
from copy import deepcopy

import pytest

from models_library.projects import Project
from pytest_simcore.helpers.utils_mock import future_with_result
# from simcore_postgres_database.models.projects import projects as projects_table
from simcore_service_webserver.log import setup_logging
from simcore_service_webserver.studies_dispatcher._core import _FILETYPE_TO_VIEWER
from simcore_service_webserver.studies_dispatcher._projects import (
    UserInfo,
    ViewerInfo,
    add_new_project,
    create_viewer_project_model,
)
from pytest_simcore.helpers.utils_login import NewUser


@pytest.fixture
def app_cfg(default_app_cfg, aiohttp_unused_port, qx_client_outdir, redis_service):
    """App's configuration used for every test in this module

    NOTE: Overrides services/web/server/tests/unit/with_dbs/conftest.py::app_cfg to influence app setup
    """
    cfg = deepcopy(default_app_cfg)

    cfg["main"]["port"] = aiohttp_unused_port()
    cfg["main"]["client_outdir"] = str(qx_client_outdir)
    cfg["main"]["studies_access_enabled"] = True

    exclude = {
        "tracing",
        "director",
        "smtp",
        "storage",
        "activity",
        "diagnostics",
        "groups",
        "tags",
        "publications",
        "catalog",
        "computation",
        "studies_access",
    }
    include = {
        "db",
        "rest",
        "projects",
        "login",
        "socketio",
        "resource_manager",
        "users",
        "products",
        "studies_dispatcher",
    }

    assert include.intersection(exclude) == set()

    for section in include:
        cfg[section]["enabled"] = True
    for section in exclude:
        cfg[section]["enabled"] = False

    # NOTE: To see logs, use pytest -s --log-cli-level=DEBUG
    setup_logging(level=logging.DEBUG)

    # Enforces smallest GC in the background task
    cfg["resource_manager"]["garbage_collection_interval_seconds"] = 1

    return cfg

from simcore_service_webserver.groups_api import auto_add_user_to_groups
from simcore_service_webserver.users_api import get_user

@pytest.mark.parametrize(
    "file_type,viewer", [(k, v) for k, v in _FILETYPE_TO_VIEWER.items()]
)
async def test_add_new_project(
    file_type: str,
    viewer: ViewerInfo,
    client,
    mocker,
):
    update_func = mocker.patch(
        "simcore_service_webserver.director_v2.create_or_update_pipeline",
        return_value=future_with_result(result=None),
    )

    # ----
    async with NewUser() as user_db:

        await auto_add_user_to_groups(client.app, user_db["id"])
        user_db = await get_user(client.app, user_db["id"])

        user = UserInfo(
            id=user_db["id"],
            name=user_db["name"],
            primary_gid=user_db["primary_gid"],
            email=user_db["email"],
        )

        project: Project = create_viewer_project_model(
            project_id="e3ee7dfc-25c3-11eb-9fae-02420a01b846",
            file_picker_id="4c69c0ce-00e4-4bd5-9cf0-59b67b3a9343",
            viewer_id="fc718e5a-bf07-4abe-b526-d9cafd34830c",
            owner=user,
            download_link="http://httpbin.org/image/jpeg",
            viewer_info=viewer,
        )

        await add_new_project(client.app, project, user)
        assert update_func.called
