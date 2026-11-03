# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

"""Cross-module check for the past-the-end pagination contract.

Requests a page past the end of the workspaces collection and asserts HTTP 200 with an
empty page carrying the real total -- proving the lenient contract is platform-wide
(shared response model), not specific to conversations.
"""

from collections.abc import AsyncIterator

import pytest
from aiohttp.test_utils import TestClient
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.webserver_login import UserInfoDict
from servicelib.aiohttp import status
from simcore_service_webserver.db.models import UserRole
from simcore_service_webserver.projects.models import ProjectDict
from yarl import URL


@pytest.fixture
def user_role() -> UserRole:
    return UserRole.USER


async def test_list_workspaces_offset_past_total_returns_200_empty_page(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    workspaces_clean_db: AsyncIterator[None],
):
    assert client.app
    url = client.app.router["list_workspaces"].url_for()

    # baseline: one workspace exists so total == 1
    resp = await client.get(f"{url}")
    data, _, meta, _links = await assert_status(resp, status.HTTP_200_OK, include_meta=True, include_links=True)
    total = meta["total"]
    assert len(data) == total

    # ask far past the end -> empty page, real total (was HTTP 500)
    resp = await client.get(f"{url.with_query({'offset': total + 100})}")
    data, _, meta, links = await assert_status(resp, status.HTTP_200_OK, include_meta=True, include_links=True)

    assert data == []
    assert meta["total"] == total
    assert meta["count"] == 0
    assert links["next"] is None
    for link in (links["self"], links["first"], links["prev"], links["last"]):
        if link is not None:
            assert int(URL(link).query["offset"]) >= 0
