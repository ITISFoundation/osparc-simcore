# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import asyncio
from collections.abc import Awaitable, Callable
from http import HTTPStatus
from math import ceil
from typing import Any

import pytest
from aiohttp.test_utils import TestClient
from aioresponses import aioresponses
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.webserver_parametrizations import (
    ExpectedResponse,
    standard_role_response,
)
from servicelib.aiohttp import status
from simcore_service_webserver._meta import api_version_prefix
from simcore_service_webserver.db.models import UserRole
from simcore_service_webserver.projects.models import ProjectDict
from simcore_service_webserver.utils import to_datetime
from yarl import URL


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
    expected: HTTPStatus,
    query_parameters: dict | None = None,
    expected_error_msg: str | None = None,
    expected_error_code: str | None = None,
) -> tuple[list[dict], dict[str, Any], dict[str, Any]]:
    if not query_parameters:
        query_parameters = {}
    # GET /v0/projects
    url = client.app.router["list_projects"].url_for()
    assert f"{url}" == f"/{api_version_prefix}/projects"
    if query_parameters:
        url = url.with_query(**query_parameters)

    resp = await client.get(f"{url}")
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


def standard_user_role() -> tuple[str, tuple[UserRole, ExpectedResponse]]:
    all_roles = standard_role_response()

    return (all_roles[0], [pytest.param(*all_roles[1][2], id="standard user role")])


@pytest.mark.parametrize(
    "limit, offset, expected_error_msg",
    [
        (-7, 0, "Input should be greater than or equal to 1"),
        (0, 0, "Input should be greater than or equal to 1"),
        (43, -2, "Input should be greater than or equal to 0"),
    ],
)
@pytest.mark.parametrize(*standard_user_role())
async def test_list_projects_with_invalid_pagination_parameters(
    client: TestClient,
    logged_user: dict[str, Any],
    primary_group: dict[str, str],
    expected: ExpectedResponse,
    storage_subsystem_mock,
    catalog_subsystem_mock: Callable[[list[ProjectDict]], None],
    director_v2_service_mock: aioresponses,
    project_db_cleaner,
    limit: int,
    offset: int,
    expected_error_msg: str,
):
    await _list_projects(
        client,
        status.HTTP_422_UNPROCESSABLE_ENTITY,
        query_parameters={"limit": limit, "offset": offset},
        expected_error_msg=expected_error_msg,
        expected_error_code="greater_than_equal",
    )


@pytest.mark.parametrize("limit", [7, 20, 43])
@pytest.mark.parametrize(*standard_user_role())
async def test_list_projects_with_pagination(
    client: TestClient,
    logged_user: dict[str, Any],
    primary_group: dict[str, str],
    expected: ExpectedResponse,
    storage_subsystem_mock,
    catalog_subsystem_mock: Callable[[list[ProjectDict]], None],
    director_v2_service_mock: aioresponses,
    project_db_cleaner,
    limit: int,
    request_create_project: Callable[..., Awaitable[ProjectDict]],
):
    NUM_PROJECTS = 60
    # let's create a few projects here
    created_projects = await asyncio.gather(
        *[
            request_create_project(
                client, expected.accepted, expected.created, logged_user, primary_group
            )
            for i in range(NUM_PROJECTS)
        ]
    )
    if expected.created == status.HTTP_201_CREATED:
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
