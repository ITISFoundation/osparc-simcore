# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name


import json

from simcore_service_catalog.__main__ import the_app

def test_openapi_json_is_updated(project_slug_dir):
    openapi_path = project_slug_dir / "openapi.json"
    assert openapi_path.exists(), "Missing required oas file"

    openapi_in_place = json.loads(openapi_path.read_text())
    openapi_in_app = the_app.openapi()
    assert openapi_in_place == openapi_in_app, "Missed to run 'make openapi-specs' ???"
