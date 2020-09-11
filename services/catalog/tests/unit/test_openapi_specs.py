# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import pytest
import json
from simcore_service_catalog.core.application import init_app


@pytest.mark.skip(reason="FIXME: fails with make tests but does not fail with pytest test_!???")
def test_openapi_json_is_updated(project_slug_dir, devel_environ):
    # devel_environ needed to build app

    app = init_app()

    openapi_path = project_slug_dir / "openapi.json"
    assert openapi_path.exists(), "Missing required oas file"

    openapi_in_place = json.loads(openapi_path.read_text())
    openapi_in_app = app.openapi()
    assert openapi_in_place == openapi_in_app, "Missed to run 'make openapi-specs' ???"
