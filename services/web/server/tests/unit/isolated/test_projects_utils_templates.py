# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import json

import pytest
from simcore_service_webserver.projects._projects_service_utils import (
    _VARIABLE_PATTERN,
    substitute_parameterized_inputs,
)
from yarl import URL


@pytest.fixture
def mock_parametrized_project(fake_data_dir):
    path = fake_data_dir / "parametrized_project.json"
    with path.open() as fh:
        prj = json.load(fh)

    # check parameterized
    inputs = prj["workbench"]["de2578c5-431e-409d-998c-c1f04de67f8b"]["inputs"]
    assert _VARIABLE_PATTERN.match(inputs["Na"])
    assert _VARIABLE_PATTERN.match(inputs["BCL"])
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
