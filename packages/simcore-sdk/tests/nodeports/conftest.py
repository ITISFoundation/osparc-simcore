 #pylint: disable=W0621
import json
import sys
import uuid
from pathlib import Path
from typing import Any, List, Tuple

import pytest
from simcore_sdk.nodeports import config
from simcore_sdk.models.pipeline_models import (Base, ComputationalPipeline,
                                                ComputationalTask)

sys.path.append(str(Path(__file__).parent / "helpers"))

pytest_plugins = ["tests.fixtures.postgres", "tests.fixtures.minio-fix"]

@pytest.fixture(scope='session')
def here()->Path:
    yield Path(__file__).parent

@pytest.fixture(scope='session')
def docker_compose_file(pytestconfig, here): # pylint:disable=unused-argument
    my_path = here /'docker-compose.yml'
    yield my_path

@pytest.fixture
def default_configuration_file(here):
    yield here / "config" / "default_config.json"

@pytest.fixture
def empty_configuration_file(here):
    yield here / "config" / "empty_config.json"

@pytest.fixture(scope='module')
def postgres(engine, session):
    # prepare database with default configuration
    Base.metadata.create_all(engine)
    yield session

@pytest.fixture()
def default_configuration(postgres, default_configuration_file):
    # prepare database with default configuration
    json_configuration = default_configuration_file.read_text()
    
    project_id = _create_new_pipeline(postgres)
    node_uuid = _set_configuration(postgres, project_id, json_configuration)
    config_dict = json.loads(json_configuration)
    config.NODE_UUID = str(node_uuid)
    config.PROJECT_ID = str(project_id)
    yield config_dict

@pytest.fixture()
def node_link():
    def create_node_link(key:str):
        return {"nodeUuid":"TEST_NODE_UUID", "output":key}
    yield create_node_link

@pytest.fixture()
def store_link(s3_client, bucket):
    def create_store_link(file_path:Path):
        # upload the file to S3
        assert Path(file_path).exists()
        s3_client.upload_file(bucket, Path(file_path).name, str(file_path))
        return {"store":"s3-z43", "path":Path(file_path).name}
    yield create_store_link

@pytest.fixture()
def special_configuration(postgres, empty_configuration_file: Path):
    def create_config(inputs: List[Tuple[str, str, Any]] =None, outputs: List[Tuple[str, str, Any]] =None):
        config_dict = json.loads(empty_configuration_file.read_text())
        _assign_config(config_dict, "inputs", inputs)
        _assign_config(config_dict, "outputs", outputs)

        project_id = _create_new_pipeline(postgres)
        node_uuid = _set_configuration(postgres, project_id, json.dumps(config_dict))
        config.NODE_UUID = str(node_uuid)
        config.PROJECT_ID = str(project_id)
        return config_dict, project_id, node_uuid
    yield create_config

@pytest.fixture()
def special_2nodes_configuration(postgres, empty_configuration_file: Path):
    def create_config(prev_node_inputs: List[Tuple[str, str, Any]] =None, prev_node_outputs: List[Tuple[str, str, Any]] =None,
                    inputs: List[Tuple[str, str, Any]] =None, outputs: List[Tuple[str, str, Any]] =None):
        project_id = _create_new_pipeline(postgres)

        # create previous node
        previous_config_dict = json.loads(empty_configuration_file.read_text())
        _assign_config(previous_config_dict, "inputs", prev_node_inputs)
        _assign_config(previous_config_dict, "outputs", prev_node_outputs)
        previous_node_uuid = _set_configuration(postgres, project_id, json.dumps(previous_config_dict))

        # create current node
        config_dict = json.loads(empty_configuration_file.read_text())
        _assign_config(config_dict, "inputs", inputs)
        _assign_config(config_dict, "outputs", outputs)
        # configure links if necessary
        str_config = json.dumps(config_dict)
        str_config = str_config.replace("TEST_NODE_UUID", str(previous_node_uuid))
        config_dict = json.loads(str_config)
        node_uuid = _set_configuration(postgres, project_id, str_config)
        config.NODE_UUID = str(node_uuid)
        config.PROJECT_ID = str(project_id)
        return config_dict, project_id, node_uuid
    yield create_config

def _create_new_pipeline(session)->str:    
    new_Pipeline = ComputationalPipeline(project_id=str(uuid.uuid4()))
    session.add(new_Pipeline)
    session.commit()
    return new_Pipeline.project_id

def _set_configuration(session, project_id: str, json_configuration: str):
    node_uuid = uuid.uuid4()
    json_configuration = json_configuration.replace("SIMCORE_NODE_UUID", str(node_uuid))
    configuration = json.loads(json_configuration)

    new_Node = ComputationalTask(project_id=project_id, node_id=node_uuid, schema=configuration["schema"], inputs=configuration["inputs"], outputs=configuration["outputs"])
    session.add(new_Node)
    session.commit()    
    return node_uuid

def _assign_config(config_dict:dict, port_type:str, entries: List[Tuple[str, str, Any]]):
    if entries is None:
        return
    for entry in entries:
        config_dict["schema"][port_type].update({
            entry[0]:{
                "label":"some label",
                "description": "some description",
                "displayOrder":2,
                "type": entry[1]
            }
        })
        if not entry[2] is None:
            config_dict[port_type].update({
                entry[0]:entry[2]
            })
