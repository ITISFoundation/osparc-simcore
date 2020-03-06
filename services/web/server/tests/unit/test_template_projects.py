# pylint:disable=wildcard-import
# pylint:disable=unused-import
# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import json
from pathlib import Path
from typing import Dict

import aiohttp
import pytest
from jsonschema import SchemaError, ValidationError
from servicelib.jsonschema_specs import create_jsonschema_specs
from servicelib.jsonschema_validation import validate_instance
from simcore_service_webserver.projects.projects_fakes import Fake
from simcore_service_webserver.projects.projects_utils import (
    substitute_parameterized_inputs,
    variable_pattern,
)
from simcore_service_webserver.resources import resources
from yarl import URL


@pytest.fixture
async def project_specs(loop, project_schema_file: Path) -> Dict:
    # should not raise any exception
    try:
        specs = await create_jsonschema_specs(project_schema_file, session=None)
    except SchemaError:
        pytest.fail("validation of schema {} failed".format(project_schema_file))
    else:
        yield specs


@pytest.fixture
def fake_db():
    Fake.reset()
    Fake.load_template_projects()
    yield Fake
    Fake.reset()


@pytest.fixture
def mock_parametrized_project(fake_data_dir):
    path = fake_data_dir / "parametrized_project.json"
    with path.open() as fh:
        prj = json.load(fh)

    # check parameterized
    inputs = prj["workbench"]["template-uuid-409d-998c-c1f04de67f8b"]["inputs"]
    assert variable_pattern.match(inputs["Na"])
    assert variable_pattern.match(inputs["BCL"])
    return prj


async def test_validate_templates(loop, project_specs: Dict, fake_db):
    for pid, project in fake_db.projects.items():
        try:
            validate_instance(project.data, project_specs)
        except ValidationError:
            pytest.fail("validation of project {} failed".format(pid))


def test_substitutions(mock_parametrized_project):

    template_id = mock_parametrized_project["uuid"]
    url = URL(f"https://myplatform/study/{template_id}").with_query(
        my_Na="33", my_BCL="54.0"
    )

    prj = substitute_parameterized_inputs(mock_parametrized_project, dict(url.query))
    assert prj
    assert (
        prj["workbench"]["template-uuid-409d-998c-c1f04de67f8b"]["inputs"]["Na"] == 33
    )
    assert (
        prj["workbench"]["template-uuid-409d-998c-c1f04de67f8b"]["inputs"]["BCL"]
        == 54.0
    )
