# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import osparc
import pytest
from osparc.models import Meta


@pytest.fixture(scope="module")
def meta_api(api_client):
    return osparc.MetaApi(api_client)


def test_get_service_metadata(meta_api):
    print("get Service Metadata", "-" * 10)
    meta: Meta = meta_api.get_service_metadata()
    print(meta)
    assert isinstance(meta, Meta)

    meta, status_code, headers = meta_api.get_service_metadata_with_http_info()

    assert isinstance(meta, Meta)
    assert status_code == 200
