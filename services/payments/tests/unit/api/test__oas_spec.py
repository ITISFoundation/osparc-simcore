# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import json
from pathlib import Path

from fastapi.testclient import TestClient


def test_openapi_json_is_in_sync_with_app_oas(
    client: TestClient, project_slug_dir: Path
):
    """
    If this test fails, just 'make openapi.json'
    """
    assert client.app

    spec_from_app = client.app.openapi()
    open_api_json_file = project_slug_dir / "openapi.json"
    stored_openapi_json_file = json.loads(open_api_json_file.read_text())
    assert (
        spec_from_app == stored_openapi_json_file
    ), "rerun `make openapi.json` and check differences"
