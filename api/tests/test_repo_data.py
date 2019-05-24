""" Keeps up-to-date all mock data in repo with schemas

"""
# pylint:disable=wildcard-import
# pylint:disable=unused-import
# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import json
from pathlib import Path
from typing import Dict, List

import jsonschema
import pytest
import yaml


def _load_data(fpath: Path):
    with open(fpath) as fh:
        try:
            data = json.load(fh)
        except json.JSONDecodeError:
            data = yaml.load(fh)
    return data


SYNCED_VERSIONS_SUFFIX = [".json", "-converted.yaml"]

PROJECTS_PATHS = [
    "services/web/server/tests/data/fake-project.json",
    "services/web/server/tests/integration/computation/workbench_sleeper_payload.json",
    "services/web/server/src/simcore_service_webserver/data/fake-template-projects.isan.json",
    "services/web/server/src/simcore_service_webserver/data/fake-user-projects.json",
    "services/web/server/src/simcore_service_webserver/data/fake-template-projects.osparc.json",
    "services/web/server/src/simcore_service_webserver/data/fake-template-projects.json",
]

# TODO: check schemas here!?
# ./src/simcore_service_webserver/data/fake-materialDB-LF-getItemList.json
# ./src/simcore_service_webserver/data/fake-modeler-LF-getItemList.json
# ./src/simcore_service_webserver/data/fake-materialDB-LF-getItem.json
# ./src/simcore_service_webserver/data/fake-materialDB-LF-Material2Entities.json
# ./tests/integration/computation/workbench_sleeper_dag_adjacency_list.json
# ./tests/integration/computation/workbench_sleeper_payload.json


@pytest.fixture(
    scope="module",
    params=SYNCED_VERSIONS_SUFFIX
)
def project_schema(request, api_specs_dir):
    suffix = request.param
    schema_path = api_specs_dir / "webserver/v0/components/schemas/project-v0.0.1{}".format(suffix)
    return _load_data(schema_path)


@pytest.fixture(
    scope="module",
    params=SYNCED_VERSIONS_SUFFIX
)
def workbench_schema(request, api_specs_dir):
    suffix = request.param
    schema_path = api_specs_dir / "webserver/v0/components/schemas/workbench{}".format(suffix)
    return _load_data(schema_path)

# TESTS --------------------------------------------------

# TODO: find json files under services with the workd project??
@pytest.mark.parametrize("data_path", PROJECTS_PATHS)
def test_project_against_schema(data_path, project_schema, this_repo_root_dir):

    data = _load_data(this_repo_root_dir / data_path)

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
def test_workbench_against_schema(data_path, workbench_schema, this_repo_root_dir):
    """
        NOTE: failures here normally are due to lack of sync between

        api/specs/webserver/v0/components/schemas/workbench.json and

        api/specs/webserver/v0/components/schemas/project-v0.0.1.json
    """
    data = _load_data(this_repo_root_dir / data_path)

    assert any(isinstance(data, _type) for _type in [List, Dict])
    if isinstance(data, Dict):
        data = [data,]

    for project_data in data:
        jsonschema.validate(project_data["workbench"], workbench_schema)
