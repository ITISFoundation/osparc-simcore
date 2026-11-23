# pylint: disable=protected-access
# pylint: disable=redefined-outer-name

import json

import pytest
from aiohttp import web
from aiohttp.test_utils import make_mocked_request
from servicelib.aiohttp import status
from simcore_service_webserver.director_v2._controller._rest_exceptions import (
    _exceptions_handlers_map as director_v2_handlers_map,
)
from simcore_service_webserver.projects._controller._rest_exceptions import (
    _handlers as projects_handlers_map,
)
from simcore_service_webserver.projects.exceptions import ProjectProductMismatchError


@pytest.fixture
def fake_request() -> web.Request:
    return make_mocked_request("POST", "/v0/computations/some-project")


async def test_product_mismatch_error_renders_identically_in_all_domains(
    fake_request: web.Request,
):
    """The guard is owned by projects; other domains must render it the same way."""
    error = ProjectProductMismatchError(
        claimed_product_name="osparc",
        project_product_name="other-product",
    )

    projects_response = await projects_handlers_map[ProjectProductMismatchError](fake_request, error)
    director_v2_response = await director_v2_handlers_map[ProjectProductMismatchError](fake_request, error)

    assert projects_response.status == status.HTTP_400_BAD_REQUEST
    assert director_v2_response.status == status.HTTP_400_BAD_REQUEST
    assert isinstance(projects_response, web.Response)
    assert isinstance(director_v2_response, web.Response)
    assert projects_response.text == director_v2_response.text

    error_body = json.loads(projects_response.text or "")
    assert error_body["error"]["message"] == ("The project belongs to a different product than the one requested.")
