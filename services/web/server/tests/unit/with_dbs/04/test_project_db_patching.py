# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=no-value-for-parameter
# pylint:disable=redefined-outer-name

import asyncio
from copy import deepcopy
from itertools import combinations
from random import randint
from typing import Any, Dict, List, Tuple
from uuid import UUID, uuid5

import pytest
import sqlalchemy as sa
from aiohttp.test_utils import TestClient
from simcore_service_webserver.db_models import UserRole
from simcore_service_webserver.projects.projects_db import (
    APP_PROJECT_DBAPI,
    ProjectDBAPI,
    setup_projects_db,
)
from simcore_service_webserver.utils import to_datetime
from sqlalchemy.engine.result import RowProxy


def _create_project_db(client: TestClient) -> ProjectDBAPI:
    setup_projects_db(client.app)

    assert APP_PROJECT_DBAPI in client.app
    db_api = client.app[APP_PROJECT_DBAPI]
    assert db_api
    # pylint:disable=protected-access
    assert db_api._app == client.app
    assert db_api._engine
    return db_api


@pytest.fixture()
async def db_api(client: TestClient, postgres_db: sa.engine.Engine) -> ProjectDBAPI:
    db_api = _create_project_db(client)
    yield db_api

    # clean the projects
    postgres_db.execute("DELETE FROM projects")


def _assert_added_project(
    exp_project: Dict[str, Any],
    added_project: Dict[str, Any],
    exp_overrides: Dict[str, Any],
):
    original_prj = deepcopy(exp_project)
    added_prj = deepcopy(added_project)
    # no user so the project owner has a pre-defined value
    _DIFFERENT_KEYS = ["creationDate", "lastChangeDate"]

    assert all(added_prj[k] != original_prj[k] for k in _DIFFERENT_KEYS)
    assert to_datetime(added_prj["creationDate"]) > to_datetime(
        exp_project["creationDate"]
    )
    assert to_datetime(added_prj["creationDate"]) <= to_datetime(
        added_prj["lastChangeDate"]
    )
    original_prj.update(exp_overrides)
    for k in _DIFFERENT_KEYS:
        added_prj.pop(k)
        original_prj.pop(k)
    # the rest of the keys shall be the same as the original
    assert added_prj == original_prj


def _assert_project_db_row(
    postgres_db: sa.engine.Engine, project: Dict[str, Any], **kwargs
):
    row: RowProxy = postgres_db.execute(
        f"SELECT * FROM projects WHERE \"uuid\"='{project['uuid']}'"
    ).fetchone()

    expected_db_entries = {
        "type": "STANDARD",
        "uuid": project["uuid"],
        "name": project["name"],
        "description": project["description"],
        "thumbnail": project["thumbnail"],
        "prj_owner": None,
        "workbench": project["workbench"],
        "published": False,
        "access_rights": {},
        "dev": project["dev"],
        "classifiers": project["classifiers"],
        "ui": project["ui"],
        "quality": project["quality"],
        "creation_date": to_datetime(project["creationDate"]),
        "last_change_date": to_datetime(project["lastChangeDate"]),
    }
    expected_db_entries.update(kwargs)
    for k in expected_db_entries:
        assert (
            row[k] == expected_db_entries[k]
        ), f"project column [{k}] does not correspond"
    assert row["last_change_date"] >= row["creation_date"]


@pytest.mark.parametrize(
    "user_role",
    [
        (UserRole.USER),
    ],
)
@pytest.mark.parametrize("number_of_nodes", [1, randint(250, 1000)])
async def test_patch_user_project_workbench_concurrently(
    fake_project: Dict[str, Any],
    postgres_db: sa.engine.Engine,
    logged_user: Dict[str, Any],
    primary_group: Dict[str, str],
    db_api: ProjectDBAPI,
    number_of_nodes: int,
):
    _NUMBER_OF_NODES = number_of_nodes
    BASE_UUID = UUID("ccc0839f-93b8-4387-ab16-197281060927")
    node_uuids = [str(uuid5(BASE_UUID, f"{n}")) for n in range(_NUMBER_OF_NODES)]
    # create a project with a lot of nodes
    fake_project["workbench"] = {
        node_uuids[n]: {
            "key": "simcore/services/comp/sleepers",
            "version": "1.43.5",
            "label": f"I am node {n}",
        }
        for n in range(_NUMBER_OF_NODES)
    }
    exp_project = deepcopy(fake_project)

    # add the project
    original_project = deepcopy(fake_project)
    new_project = await db_api.add_project(prj=fake_project, user_id=logged_user["id"])
    _assert_added_project(
        original_project,
        new_project,
        exp_overrides={
            "prjOwner": logged_user["email"],
            "accessRights": {
                str(primary_group["gid"]): {"read": True, "write": True, "delete": True}
            },
        },
    )
    _assert_project_db_row(
        postgres_db,
        new_project,
        prj_owner=logged_user["id"],
        access_rights={
            str(primary_group["gid"]): {"read": True, "write": True, "delete": True}
        },
    )

    # patch all the nodes concurrently
    randomly_created_outputs = [
        {"outputs": {f"out_{k}": f"{k}"} for k in range(randint(1, 10))}
        for n in range(_NUMBER_OF_NODES)
    ]
    for n in range(_NUMBER_OF_NODES):
        exp_project["workbench"][node_uuids[n]].update(randomly_created_outputs[n])
    patched_projects: List[
        Tuple[Dict[str, Any], Dict[str, Any]]
    ] = await asyncio.gather(
        *[
            db_api.patch_user_project_workbench(
                {node_uuids[n]: randomly_created_outputs[n]},
                logged_user["id"],
                new_project["uuid"],
            )
            for n in range(_NUMBER_OF_NODES)
        ]
    )
    # NOTE: each returned project contains the project with some updated workbenches
    # the ordering is uncontrolled.
    # The important thing is that the final result shall contain ALL the changes

    for (prj, changed_entries), node_uuid, exp_outputs in zip(
        patched_projects, node_uuids, randomly_created_outputs
    ):
        assert prj["workbench"][node_uuid]["outputs"] == exp_outputs["outputs"]
        assert changed_entries == {node_uuid: {"outputs": exp_outputs["outputs"]}}

    # get the latest change date
    latest_change_date = max(
        to_datetime(prj["lastChangeDate"]) for prj, _ in patched_projects
    )

    # check the nodes are completely patched as expected
    _assert_project_db_row(
        postgres_db,
        exp_project,
        prj_owner=logged_user["id"],
        access_rights={
            str(primary_group["gid"]): {"read": True, "write": True, "delete": True}
        },
        creation_date=to_datetime(new_project["creationDate"]),
        last_change_date=latest_change_date,
    )

    # now concurrently remove the outputs
    for n in range(_NUMBER_OF_NODES):
        exp_project["workbench"][node_uuids[n]]["outputs"] = {}
    patched_projects: List[
        Tuple[Dict[str, Any], Dict[str, Any]]
    ] = await asyncio.gather(
        *[
            db_api.patch_user_project_workbench(
                {node_uuids[n]: {"outputs": {}}},
                logged_user["id"],
                new_project["uuid"],
            )
            for n in range(_NUMBER_OF_NODES)
        ]
    )

    # get the latest change date
    latest_change_date = max(
        to_datetime(prj["lastChangeDate"]) for prj, _ in patched_projects
    )

    # check the nodes are completely patched as expected
    _assert_project_db_row(
        postgres_db,
        exp_project,
        prj_owner=logged_user["id"],
        access_rights={
            str(primary_group["gid"]): {"read": True, "write": True, "delete": True}
        },
        creation_date=to_datetime(new_project["creationDate"]),
        last_change_date=latest_change_date,
    )

    # now concurrently remove the outputs
    for n in range(_NUMBER_OF_NODES):
        exp_project["workbench"][node_uuids[n]]["outputs"] = {}
    patched_projects: List[
        Tuple[Dict[str, Any], Dict[str, Any]]
    ] = await asyncio.gather(
        *[
            db_api.patch_user_project_workbench(
                {node_uuids[n]: {"outputs": {}}},
                logged_user["id"],
                new_project["uuid"],
            )
            for n in range(_NUMBER_OF_NODES)
        ]
    )

    # get the latest change date
    latest_change_date = max(
        to_datetime(prj["lastChangeDate"]) for prj, _ in patched_projects
    )

    # check the nodes are completely patched as expected
    _assert_project_db_row(
        postgres_db,
        exp_project,
        prj_owner=logged_user["id"],
        access_rights={
            str(primary_group["gid"]): {"read": True, "write": True, "delete": True}
        },
        creation_date=to_datetime(new_project["creationDate"]),
        last_change_date=latest_change_date,
    )
