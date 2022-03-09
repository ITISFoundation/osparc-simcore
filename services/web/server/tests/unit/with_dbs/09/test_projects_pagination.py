# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import asyncio
from copy import deepcopy
from math import ceil
from typing import Any, Callable, Dict, List, Optional, Tuple, Type, Union

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from aioresponses import aioresponses
from models_library.projects_state import ProjectState
from pytest_simcore.aioresponses_mocker import AioResponsesMock
from pytest_simcore.helpers.utils_assert import assert_status
from pytest_simcore.helpers.utils_webserver_projects import (
    ExpectedResponse,
    standard_role_response,
)
from simcore_service_webserver._meta import api_version_prefix
from simcore_service_webserver.db_models import UserRole
from simcore_service_webserver.projects.projects_handlers_crud import (
    OVERRIDABLE_DOCUMENT_KEYS,
)
from simcore_service_webserver.utils import now_str, to_datetime
from yarl import URL

API_PREFIX = "/" + api_version_prefix


# HELPERS -----------------------------------------------------------------------------------------


def assert_replaced(current_project, update_data):
    def _extract(dikt, keys):
        return {k: dikt[k] for k in keys}

    modified = [
        "lastChangeDate",
    ]
    keep = [k for k in update_data.keys() if k not in modified]

    assert _extract(current_project, keep) == _extract(update_data, keep)

    k = "lastChangeDate"
    assert to_datetime(update_data[k]) < to_datetime(current_project[k])


async def _list_projects(
    client,
    expected: Type[web.HTTPException],
    query_parameters: Optional[Dict] = None,
    expected_error_msg: Optional[str] = None,
    expected_error_code: Optional[str] = None,
) -> Tuple[List[Dict], Dict[str, Any], Dict[str, Any]]:
    if not query_parameters:
        query_parameters = {}
    # GET /v0/projects
    url = client.app.router["list_projects"].url_for()
    assert str(url) == API_PREFIX + "/projects"
    if query_parameters:
        url = url.with_query(**query_parameters)

    resp = await client.get(url)
    data, errors, meta, links = await assert_status(
        resp,
        expected,
        expected_msg=expected_error_msg,
        expected_error_code=expected_error_code,
        include_meta=True,
        include_links=True,
    )
    if data:
        assert meta is not None
        # see [api/specs/webserver/openapi-projects.yaml] for defaults
        exp_offset = max(int(query_parameters.get("offset", 0)), 0)
        exp_limit = max(1, min(int(query_parameters.get("limit", 20)), 50))
        assert meta["offset"] == exp_offset
        assert meta["limit"] == exp_limit
        exp_last_page = ceil(meta["total"] / meta["limit"] - 1)
        assert links is not None
        complete_url = client.make_url(url)
        assert links["self"] == str(
            URL(complete_url).update_query({"offset": exp_offset, "limit": exp_limit})
        )
        assert links["first"] == str(
            URL(complete_url).update_query({"offset": 0, "limit": exp_limit})
        )
        assert links["last"] == str(
            URL(complete_url).update_query(
                {"offset": exp_last_page * exp_limit, "limit": exp_limit}
            )
        )
        if exp_offset <= 0:
            assert links["prev"] == None
        else:
            assert links["prev"] == str(
                URL(complete_url).update_query(
                    {"offset": max(exp_offset - exp_limit, 0), "limit": exp_limit}
                )
            )
        if exp_offset >= (exp_last_page * exp_limit):
            assert links["next"] == None
        else:
            assert links["next"] == str(
                URL(complete_url).update_query(
                    {
                        "offset": min(
                            exp_offset + exp_limit, exp_last_page * exp_limit
                        ),
                        "limit": exp_limit,
                    }
                )
            )
    else:
        assert meta is None
        assert links is None
    return data, meta, links


async def _new_project(
    client,
    expected_response: Type[web.HTTPException],
    logged_user: Dict[str, str],
    primary_group: Dict[str, str],
    *,
    project: Optional[Dict] = None,
    from_template: Optional[Dict] = None,
) -> Dict:
    # POST /v0/projects
    url = client.app.router["create_projects"].url_for()
    assert str(url) == f"{API_PREFIX}/projects"
    if from_template:
        url = url.with_query(from_template=from_template["uuid"])

    # Pre-defined fields imposed by required properties in schema
    project_data = {}
    expected_data = {}
    if from_template:
        # access rights are replaced
        expected_data = deepcopy(from_template)
        expected_data["accessRights"] = {}

    if not from_template or project:
        project_data = {
            "uuid": "0000000-invalid-uuid",
            "name": "Minimal name",
            "description": "this description should not change",
            "prjOwner": "me but I will be removed anyway",
            "creationDate": now_str(),
            "lastChangeDate": now_str(),
            "thumbnail": "",
            "accessRights": {},
            "workbench": {},
            "tags": [],
            "classifiers": [],
            "ui": {},
            "dev": {},
            "quality": {},
        }
        if project:
            project_data.update(project)

        for key in project_data:
            expected_data[key] = project_data[key]
            if (
                key in OVERRIDABLE_DOCUMENT_KEYS
                and not project_data[key]
                and from_template
            ):
                expected_data[key] = from_template[key]

    resp = await client.post(url, json=project_data)

    new_project, error = await assert_status(resp, expected_response)
    if not error:
        # has project state
        assert not ProjectState(
            **new_project.pop("state")
        ).locked.value, "Newly created projects should be unlocked"

        # updated fields
        assert expected_data["uuid"] != new_project["uuid"]
        assert (
            new_project["prjOwner"] == logged_user["email"]
        )  # the project owner is assigned the user id e-mail
        assert to_datetime(expected_data["creationDate"]) < to_datetime(
            new_project["creationDate"]
        )
        assert to_datetime(expected_data["lastChangeDate"]) < to_datetime(
            new_project["lastChangeDate"]
        )
        # the access rights are set to use the logged user primary group + whatever was inside the project
        expected_data["accessRights"].update(
            {str(primary_group["gid"]): {"read": True, "write": True, "delete": True}}
        )
        assert new_project["accessRights"] == expected_data["accessRights"]

        # invariant fields
        modified_fields = [
            "uuid",
            "prjOwner",
            "creationDate",
            "lastChangeDate",
            "accessRights",
            "workbench" if from_template else None,
            "ui" if from_template else None,
        ]

        for key in new_project.keys():
            if key not in modified_fields:
                assert expected_data[key] == new_project[key]
    return new_project


def standard_user_role() -> Tuple[str, Tuple[UserRole, ExpectedResponse]]:
    all_roles = standard_role_response()

    return (all_roles[0], [pytest.param(*all_roles[1][2], id="standard user role")])


# TESTS ----------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "limit, offset, expected_error_msg",
    [
        (-7, 0, "Invalid parameter value for `limit`"),
        (0, 0, "Invalid parameter value for `limit`"),
        (43, -2, "Invalid parameter value for `offset`"),
    ],
)
@pytest.mark.parametrize(*standard_user_role())
async def test_list_projects_with_invalid_pagination_parameters(
    client: TestClient,
    logged_user: Dict[str, Any],
    primary_group: Dict[str, str],
    expected: ExpectedResponse,
    storage_subsystem_mock,
    catalog_subsystem_mock: Callable[[Optional[Union[List[Dict], Dict]]], None],
    director_v2_service_responses_mock: AioResponsesMock,
    project_db_cleaner,
    limit: int,
    offset: int,
    expected_error_msg: str,
):
    await _list_projects(
        client,
        web.HTTPBadRequest,
        query_parameters={"limit": limit, "offset": offset},
        expected_error_msg=expected_error_msg,
        expected_error_code="InvalidParameterValue",
    )


@pytest.mark.parametrize("limit", [7, 20, 43])
@pytest.mark.parametrize(*standard_user_role())
async def test_list_projects_with_pagination(
    client: TestClient,
    logged_user: Dict[str, Any],
    primary_group: Dict[str, str],
    expected: ExpectedResponse,
    storage_subsystem_mock,
    catalog_subsystem_mock: Callable[[Optional[Union[List[Dict], Dict]]], None],
    director_v2_service_responses_mock: aioresponses,
    project_db_cleaner,
    limit: int,
):

    NUM_PROJECTS = 90
    # let's create a few projects here
    created_projects = await asyncio.gather(
        *[
            _new_project(client, expected.created, logged_user, primary_group)
            for i in range(NUM_PROJECTS)
        ]
    )
    if expected.created == web.HTTPCreated:
        catalog_subsystem_mock(created_projects)

        assert len(created_projects) == NUM_PROJECTS
        NUMBER_OF_CALLS = ceil(NUM_PROJECTS / limit)
        next_link = None
        default_query_parameter = {"limit": limit}
        projects = []
        for i in range(NUMBER_OF_CALLS):
            print(
                "calling in with query",
                next_link.query if next_link else default_query_parameter,
            )
            data, meta, links = await _list_projects(
                client,
                expected.ok,
                query_parameters=next_link.query
                if next_link
                else default_query_parameter,
            )
            print("...received [", meta, "]")
            assert len(data) == meta["count"]
            assert meta["count"] == min(limit, NUM_PROJECTS - len(projects))
            assert meta["limit"] == limit
            projects.extend(data)
            next_link = URL(links["next"]) if links["next"] is not None else None

        assert len(projects) == len(created_projects)
        assert {prj["uuid"] for prj in projects} == {
            prj["uuid"] for prj in created_projects
        }
