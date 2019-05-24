""" Keeps up-to-date all mock data in repo with schemas

"""
# pylint:disable=wildcard-import
# pylint:disable=unused-import
# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import json
from typing import Dict, List

import jsonschema
import pytest

# TODO: check schemas here!?
# ./src/simcore_service_webserver/data/fake-materialDB-LF-getItemList.json
# ./src/simcore_service_webserver/data/fake-modeler-LF-getItemList.json
# ./src/simcore_service_webserver/data/fake-materialDB-LF-getItem.json
# ./src/simcore_service_webserver/data/fake-materialDB-LF-Material2Entities.json
# ./tests/integration/computation/workbench_sleeper_dag_adjacency_list.json
# ./tests/integration/computation/workbench_sleeper_payload.json


@pytest.fixture
def project_schema(api_specs_dir):
    schema_path = api_specs_dir / "webserver/v0/components/schemas/project-v0.0.1.json"
    with open(schema_path) as fh:
        schema = json.load(fh)
    return schema

@pytest.fixture
def workbench_schema(api_specs_dir):
    schema_path = api_specs_dir / "webserver/v0/components/schemas/workbench.json"
    with open(schema_path) as fh:
        schema = json.load(fh)
    return schema


PROJECTS_PATHS = [
    "services/web/server/tests/data/fake-project.json",
    "services/web/server/tests/integration/computation/workbench_sleeper_payload.json",
    "services/web/server/src/simcore_service_webserver/data/fake-template-projects.isan.json",
    "services/web/server/src/simcore_service_webserver/data/fake-user-projects.json",
    "services/web/server/src/simcore_service_webserver/data/fake-template-projects.osparc.json",
    "services/web/server/src/simcore_service_webserver/data/fake-template-projects.json",
]


# TODO: find json files under services with the workd project??
@pytest.mark.parametrize("data_path", PROJECTS_PATHS)
def test_project_against_schema(data_path, project_schema, this_repo_root_dir):
    with open(this_repo_root_dir / data_path) as fh:
       data = json.load(fh)

    # Adapts workbench
    if "workbench" in data_path:
        # TODO:  pip install faker-schema
        #from faker_schema.faker_schema import FakerSchema
        #faker = FakerSchema()
        #prj = faker.generate_fake(project_schema)
        prj = {
            "uuid": "eiusmod",
            "name": "minim",
            "description": "ad",
            "notes": "velit fugiat",
            "prjOwner": "ullamco eu voluptate",
            "collaborators": {
                "I<h)n6{%g5o": [
                "write",
                "read",
                "read",
                "write",
                "write"
                ]
            },
            "creationDate": "8715-11-30T9:1:51.388Z",
            "lastChangeDate": "0944-02-31T5:1:7.795Z",
            "thumbnail": "labore incid",
            "workbench": data["workbench"]
        }
        data = prj

    assert any(isinstance(data, _type) for _type in [List, Dict])
    if isinstance(data, Dict):
        data = [data,]

    for project_data in data:
        jsonschema.validate(project_data, project_schema)


@pytest.mark.parametrize("data_path", PROJECTS_PATHS)
def test_workbench_against_schema(data_path, project_schema, this_repo_root_dir):
    """
        NOTE: failures here normally are due to lack of sync between

        api/specs/webserver/v0/components/schemas/workbench.json and

        api/specs/webserver/v0/components/schemas/project-v0.0.1.json
    """
    with open(this_repo_root_dir / data_path) as fh:
       data = json.load(fh)

    assert any(isinstance(data, _type) for _type in [List, Dict])
    if isinstance(data, Dict):
        data = [data,]

    for project_data in data:
        jsonschema.validate(project_data["workbench"], project_schema)
