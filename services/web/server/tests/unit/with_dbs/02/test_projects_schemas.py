# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import json
from dataclasses import dataclass
from typing import Optional
from uuid import uuid4

import pytest
from faker import Faker
from models_library.projects import Project
from models_library.projects_nodes import Node
from models_library.projects_nodes_io import NodeID, PortLink
from models_library.rest_pagination import Page
from pytest_simcore.simcore_webserver_projects_rest_api import (
    CLOSE_PROJECT,
    GET_PROJECT,
    LIST_PROJECTS,
    NEW_PROJECT,
    OPEN_PROJECT,
    REPLACE_PROJECT,
    REPLACE_PROJECT_ON_MODIFIED,
    HttpApiCallCapture,
)
from simcore_service_webserver.projects.projects_schemas import (
    ProjectCreate,
    ProjectGet,
    ProjectItem,
    ProjectReplace,
    ProjectSQLModel,
)


@pytest.mark.parametrize("api_call", (NEW_PROJECT,))
def test_new_project_models(api_call: HttpApiCallCapture):
    model = ProjectCreate.parse_obj(api_call.request_payload)

    assert api_call.response_body
    model = ProjectGet.parse_obj(api_call.response_body["data"])


@pytest.mark.parametrize("api_call", (GET_PROJECT,))
def test_get_project_models(api_call: HttpApiCallCapture):
    assert api_call.request_payload is None
    assert api_call.response_body
    model = ProjectGet.parse_obj(api_call.response_body["data"])


@pytest.mark.parametrize("api_call", (OPEN_PROJECT,))
def test_open_project_models(api_call: HttpApiCallCapture):
    # TODO: check against OAS
    assert api_call.request_payload is None
    assert api_call.response_body
    model = ProjectGet.parse_obj(api_call.response_body["data"])


@pytest.mark.parametrize("api_call", (REPLACE_PROJECT, REPLACE_PROJECT_ON_MODIFIED))
def test_replace_project_models(api_call: HttpApiCallCapture):
    assert api_call.request_payload
    model = ProjectReplace.parse_obj(api_call)

    assert api_call.response_body
    model = ProjectGet.parse_obj(api_call.response_body["data"])


@pytest.mark.parametrize("api_call", (CLOSE_PROJECT,))
def test_close_project_models(api_call: HttpApiCallCapture):
    # TODO: check against OAS
    assert api_call.request_payload is None
    assert api_call.response_body is None


@pytest.mark.parametrize("api_call", (LIST_PROJECTS,))
def test_list_project_models(api_call: HttpApiCallCapture):
    # TODO: check against OAS
    assert api_call.request_payload is None
    assert api_call.response_body

    model = Page[ProjectItem].parse_obj(api_call.response_body)


def test_db_to_api_models():
    # read from db
    db_model = ProjectSQLModel
    # common,
    # excluded
    # new -> map or transform (e.g. aggretation)

    api_model = ProjectGet.from_orm(db_model)


#


def test_build_project_model(faker: Faker):

    project = Project.parse_obj(
        {
            "uuid": faker.uuid4(),
            "name": "The project name",
            "description": faker.description(),
            "prjOwner": faker.email(),
            "accessRights": {},
            "thumbnail": None,
            "creationDate": "2019-05-24T10:36:57.813Z",
            "lastChangeDate": "2019-05-24T10:36:57.813Z",
            "workbench": {},
        }
    )

    db_project = ProjectSQLModel.from_orm(project)


def test_create_workbench(faker: Faker):

    # some tools to build pipelines
    def create_sleeper(
        label, *, input_1: Optional[str] = None, input_2: int = 2, input_3: bool = False
    ):
        schema = json.loads(
            """\
        "inputs": {
                "input_1": {
                "displayOrder": 1,
                "label": "File with int number",
                "description": "Pick a file containing only one integer",
                "type": "data:text/plain",
                "fileToKeyMap": {
                    "single_number.txt": "input_1"
                },
                "keyId": "input_1"
            },
            "input_2": {
                "displayOrder": 2,
                "label": "Sleep interval",
                "description": "Choose an amount of time to sleep",
                "type": "integer",
                "defaultValue": 2,
                "keyId": "input_2"
                },
            "input_3": {
                "displayOrder": 3,
                "label": "Fail after sleep",
                "description": "If set to true will cause service to fail after it sleeps",
                "type": "boolean",
                "defaultValue": false,
                "keyId": "input_3"
                }
        },
        "outputs": {
            "output_1": {
                "displayOrder": 1,
                "label": "File containing one random integer",
                "description": "Integer is generated in range [1-9]",
                "type": "data:text/plain",
                "fileToKeyMap": {
                    "single_number.txt": "output_1"
                },
                "keyId": "output_1"
            },
            "output_2": {
                "displayOrder": 2,
                "label": "Random sleep interval",
                "description": "Interval is generated in range [1-9]",
                "type": "integer",
                "keyId": "output_2"
            }
        },
        """
        )

        inputs = {"input_1": input_1, "input_2": input_2, "input_3": input_3}

        return Node(
            key="simcore/services/comp/itis/sleeper",
            version="1.0.0",
            label=label,
            inputs={k: v for k, v in inputs.items() if v is not None},
        )

    @dataclass
    class NetworkTool:
        workbench: dict[NodeID, Node] = {}

        def add(self, node: Node, node_id: Optional[NodeID] = None) -> NodeID:
            node_id = node_id or uuid4()
            assert node_id not in self.workbench
            self.workbench[node_id] = node
            return node_id

        def get(self, node_id: NodeID) -> Optional[Node]:
            return self.workbench.get(node_id)

        def connect(
            self,
            src_node_id: NodeID,
            src_output_name: str,
            dst_node_id: NodeID,
            dst_input_name: str,
            *,
            check_if_connected: bool = True,  # if False, it will drop previous and connects new
        ):
            src = self.workbench[src_node_id]

            assert src.outputs is not None, "source node has no output"
            assert src_output_name in src.outputs, "output does not exists"

            dst: Node = self.workbench[dst_node_id].copy(deep=True)

            assert dst.input_nodes
            if src_node_id not in dst.input_nodes:
                dst.input_nodes.append(src_node_id)

            assert dst.inputs is not None
            if check_if_connected:
                assert dst.inputs.get(dst_input_name) is None, "input already assigned!"

            # TODO: check compatibility?

            dst.inputs[dst_input_name] = PortLink(
                nodeUuid=src_node_id, output=src_output_name
            )

            # once all is checked, connection is effective now
            self.workbench[dst_node_id] = Node.parse_obj(dst.dict(exclude_unset=True))

    ntw = NetworkTool()

    sleeper_1 = ntw.add(create_sleeper("sleeper1"))
    sleeper_2 = ntw.add(create_sleeper("sleeper2"))

    ntw.connect(sleeper_1, "output_1", sleeper_2, "input_1")
    ntw.connect(sleeper_1, "output_2", sleeper_2, "input_2")

    assert {
        "fa8c4b9e-9976-4202-b9e4-415ef6b5b85e": {
            "key": "simcore/services/comp/itis/sleeper",
            "version": "2.0.2",
            "label": "sleeper",
            "inputs": {"input_2": 2, "input_3": False},
            "inputsUnits": {},
            "inputNodes": [],
            "parent": None,
            "thumbnail": "",
        },
        "0ed36b39-d624-49c5-8d54-b89b45eeaace": {
            "key": "simcore/services/comp/itis/sleeper",
            "version": "2.0.2",
            "label": "sleeper_2",
            "inputs": {
                "input_1": {
                    "nodeUuid": "fa8c4b9e-9976-4202-b9e4-415ef6b5b85e",
                    "output": "output_1",
                },
                "input_2": {
                    "nodeUuid": "fa8c4b9e-9976-4202-b9e4-415ef6b5b85e",
                    "output": "output_2",
                },
                "input_3": False,
            },
            "inputsUnits": {},
            "inputNodes": ["fa8c4b9e-9976-4202-b9e4-415ef6b5b85e"],
            "parent": None,
            "thumbnail": "",
        },
    } == {f"{k}": v.dict() for k, v in ntw.workbench.items()}
