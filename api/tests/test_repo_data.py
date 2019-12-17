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

SYNCED_VERSIONS_SUFFIX = [
    ".json",                 # json-schema specs file
    "-converted.yaml"        # equivalent openapi specs file (see scripts/json-schema-to-openapi-schema)
]


# TODO: find json files under services with the word project or similar wildcard??
PROJECTS_PATHS = [
    "services/web/server/tests/data/fake-project.json",
    "services/web/server/tests/integration/computation/workbench_sleeper_payload.json",
    "services/web/server/src/simcore_service_webserver/data/fake-template-projects.isan.json",
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

def _load_data(fpath: Path):
    with open(fpath) as fh:
        try:
            data = json.load(fh)
        except json.JSONDecodeError:
            fh.seek(0)
            data = yaml.load(fh)
    return data

@pytest.fixture(
    scope="module",
    params=SYNCED_VERSIONS_SUFFIX
)
def project_schema(request, webserver_api_dir):
    suffix = request.param
    schema_path = webserver_api_dir / "components/schemas/project-v0.0.1{}".format(suffix)
    return _load_data(schema_path)

# TESTS --------------------------------------------------

@pytest.mark.parametrize("data_path", PROJECTS_PATHS)
def test_project_against_schema(data_path, project_schema, this_repo_root_dir):
    """
        Both projects and workbench datasets are tested against the project schema
    """
    data = _load_data(this_repo_root_dir / data_path)

    # Adapts workbench-only data: embedds data within a fake project skeleton
    if "workbench" in data_path:
        # TODO: Ideally project is faked to a schema.
        # NOTE: tried already `faker-schema` but it does not do the job right
        prj = {
            "uuid": "eiusmod",
            "name": "minim",
            "description": "ad",
            "prjOwner": "ullamco eu voluptate",
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
