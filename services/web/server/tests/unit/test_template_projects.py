# pylint:disable=wildcard-import
# pylint:disable=unused-import
# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from pathlib import Path
from typing import Dict

import pytest
from jsonschema import SchemaError, ValidationError

from servicelib.jsonschema_specs import create_jsonschema_specs
from servicelib.jsonschema_validation import validate_instance
from simcore_service_webserver.projects.projects_fakes import Fake


@pytest.fixture
async def project_specs(loop, project_schema_file: Path) -> Dict:
    # should not raise any exception
    try:
        specs = await create_jsonschema_specs(project_schema_file)
        return specs
    except SchemaError:
        pytest.fail("validation of schema {} failed".format(project_schema_file))


@pytest.fixture
def fake_db():
    Fake.reset()
    Fake.load_template_projects()
    yield Fake
    Fake.reset()

async def test_validate_templates(loop, project_specs: Dict, fake_db):
    for pid, project in fake_db.projects.items():
        try:
            validate_instance(project.data, project_specs)
        except ValidationError:
            pytest.fail("validation of project {} failed".format(pid))
