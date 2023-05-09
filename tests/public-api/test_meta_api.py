# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import pytest
from osparc import ApiClient, MetaApi
from osparc.models import Meta


@pytest.fixture(scope="module")
def meta_api(api_client: ApiClient) -> MetaApi:
    return MetaApi(api_client)


def test_get_service_metadata(meta_api: MetaApi):
    meta = meta_api.get_service_metadata()
    assert isinstance(meta, Meta)

    meta, status_code, headers = meta_api.get_service_metadata_with_http_info()

    assert isinstance(meta, Meta)
    assert status_code == 200
