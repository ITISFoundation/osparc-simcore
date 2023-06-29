# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import pkg_resources
import pytest
from packaging.version import Version

try:
    pkg_resources.require("osparc>=0.5.0")
    import osparc_client

    # Use the imported package here
except pkg_resources.DistributionNotFound:
    # Package or minimum version not found
    import osparc as osparc_client


@pytest.fixture(scope="module")
def meta_api(api_client: osparc_client.ApiClient) -> osparc_client.MetaApi:
    return osparc_client.MetaApi(api_client)


def _get_client_report(api_client: osparc_client.ApiClient) -> dict[str, str]:
    report = {}
    for line in api_client.configuration.to_debug_report().split("\n"):
        key, value = line.split(":", maxsplit=1)
        report[key.strip()] = value.strip()
    return report


def test_get_service_metadata(
    meta_api: osparc_client.MetaApi, api_client: osparc_client.ApiClient
):
    meta = meta_api.get_service_metadata()
    assert isinstance(meta, osparc_client.Meta)

    # client is compatible with this API version
    report = _get_client_report(api_client)
    expected_api_version = Version(report["Version of the API"])

    current_api_version = Version(meta.version)

    assert expected_api_version <= current_api_version

    meta, status_code, headers = meta_api.get_service_metadata_with_http_info()

    assert isinstance(meta, osparc_client.Meta)
    assert status_code == 200
