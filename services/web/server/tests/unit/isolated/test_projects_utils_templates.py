# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import json
from pathlib import Path
from typing import Any, AsyncIterator, Dict

import pytest
from jsonschema import SchemaError
from servicelib.aiohttp.jsonschema_specs import create_jsonschema_specs
from simcore_service_webserver.projects.projects_utils import (
    VARIABLE_PATTERN,
    substitute_parameterized_inputs,
)
from yarl import URL


@pytest.fixture
async def project_specs(project_schema_file: Path) -> AsyncIterator[Dict[str, Any]]:
    # should not raise any exception
    try:
        specs = await create_jsonschema_specs(project_schema_file, session=None)
    except SchemaError:
        pytest.fail("validation of schema {} failed".format(project_schema_file))
    else:
        yield specs


@pytest.fixture
def mock_parametrized_project(fake_data_dir):
    path = fake_data_dir / "parametrized_project.json"
    with path.open() as fh:
        prj = json.load(fh)

    # check parameterized
    inputs = prj["workbench"]["de2578c5-431e-409d-998c-c1f04de67f8b"]["inputs"]
    assert VARIABLE_PATTERN.match(inputs["Na"])
    assert VARIABLE_PATTERN.match(inputs["BCL"])
    return prj


def test_substitutions(mock_parametrized_project):

    template_id = mock_parametrized_project["uuid"]
    url = URL(f"https://myplatform/study/{template_id}").with_query(
        my_Na="33", my_BCL="54.0"
    )

    prj = substitute_parameterized_inputs(mock_parametrized_project, dict(url.query))
    assert prj
    assert (
        prj["workbench"]["de2578c5-431e-409d-998c-c1f04de67f8b"]["inputs"]["Na"] == 33
    )
    assert (
        prj["workbench"]["de2578c5-431e-409d-998c-c1f04de67f8b"]["inputs"]["BCL"]
        == 54.0
    )
