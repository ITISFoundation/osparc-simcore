# pylint:disable=wildcard-import
# pylint:disable=unused-import
# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import json
from copy import deepcopy

import jsonschema
import pytest
from jsonschema import ValidationError

from simcore_service_webserver.projects.projects_utils import clone_project_document
from simcore_service_webserver.resources import resources


def load_template_projects():
    projects = []
    projects_names = [
        name for name in resources.listdir("data") if "template-projects" in name
    ]
    for name in projects_names:
        with resources.stream(f"data/{name}") as fp:
            projects.extend(json.load(fp))
    return projects


@pytest.fixture
def project_schema(project_schema_file):
    with open(project_schema_file) as fh:
        schema = json.load(fh)
    return schema


@pytest.mark.parametrize(
    "name,project", [(p["name"], p) for p in load_template_projects()]
)
def test_clone_project_document(name, project, project_schema):

    source = deepcopy(project)
    clone, _ = clone_project_document(source)

    # was not modified by clone_project_document
    assert source == project

    # valid clone
    assert clone["uuid"] != project["uuid"]

    node_ids = project["workbench"].keys()
    for clone_node_id in clone["workbench"]:
        assert clone_node_id not in node_ids

    try:
        jsonschema.validate(instance=clone, schema=project_schema)
    except ValidationError as err:
        pytest.fail(f"Invalid clone of '{name}': {err.message}")
