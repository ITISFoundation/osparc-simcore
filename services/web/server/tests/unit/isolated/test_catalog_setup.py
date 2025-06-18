# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from collections.abc import Awaitable, Callable

import pytest
from aiohttp.test_utils import TestClient
from servicelib.aiohttp.application import create_safe_application
from simcore_service_webserver._meta import api_version_prefix
from simcore_service_webserver.catalog import catalog_service
from simcore_service_webserver.catalog.plugin import setup_catalog
from yarl import URL


@pytest.fixture
async def client(
    aiohttp_client: Callable[..., Awaitable[TestClient]],
):
    app = create_safe_application()

    setup_catalog.__wrapped__(app)

    return await aiohttp_client(app)


def test_url_translation():
    front_url = URL(
        f"https://osparc.io/{api_version_prefix}/catalog/dags/123?page_size=6"
    )

    rel_url = front_url.relative()
    assert rel_url.path.startswith(f"/{api_version_prefix}/catalog")

    api_target_origin = URL("http://catalog:8000")
    api_target_url = catalog_service.to_backend_service(
        rel_url, api_target_origin, "v5"
    )

    assert str(api_target_url) == "http://catalog:8000/v5/dags/123?page_size=6"
