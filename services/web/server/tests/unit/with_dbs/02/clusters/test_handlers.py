# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name


from typing import Any, Dict

import pytest
from _helpers import ExpectedResponse, standard_role_response
from aiohttp.test_utils import TestClient
from pytest_simcore.helpers.utils_assert import assert_status


@pytest.mark.parametrize(
    *standard_role_response(),
)
async def test_list_clusters(
    enable_dev_features: None,
    client: TestClient,
    logged_user: Dict[str, Any],
    expected: ExpectedResponse,
):
    url = client.app.router["list_clusters_handler"].url_for()
    rsp = await client.get(f"{url}")
    data, error = await assert_status(rsp, expected.ok)


def test_create_cluster(client: TestClient):
    pass


def test_get_cluster(client: TestClient):
    pass


def test_update_cluster(client: TestClient):
    pass


def test_delete_cluster(client: TestClient):
    pass
