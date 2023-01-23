# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from typing import Any

from fastapi.testclient import TestClient


def test_openapi_json_is_in_sync_with_app_oas(
    client: TestClient, openapi_specs: dict[str, Any]
):
    """
    If this test fails, just 'make openapi.json'
    """
    spec_from_app = client.app.openapi()
    stored_openapi_json_file = openapi_specs.copy()
    assert (
        spec_from_app == stored_openapi_json_file
    ), "rerun `make openapi.json` and check differences"
