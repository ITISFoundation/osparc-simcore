 #pylint: disable=W0621
import json
import os
import sys
import uuid
from pathlib import Path
from typing import Any, List, Tuple

import pytest

from simcore_sdk.models.pipeline_models import (Base, ComputationalPipeline,
                                                ComputationalTask)

sys.path.append(os.path.join(os.path.dirname(__file__), "helpers"))

pytest_plugins = ["tests.fixtures.postgres", "tests.fixtures.minio-fix"]

@pytest.fixture(scope='session')
def docker_compose_file(pytestconfig): # pylint:disable=unused-argument
    my_path = os.path.join(os.path.dirname(__file__), 'docker-compose.yml')
    return my_path


def _create_new_pipeline(engine, session)->str:
    # prepare database with default configuration
    Base.metadata.create_all(engine)
    new_Pipeline = ComputationalPipeline()
    session.add(new_Pipeline)
    session.commit()

    os.environ["SIMCORE_PIPELINE_ID"]=str(new_Pipeline.pipeline_id)

    return new_Pipeline.pipeline_id

def _set_configuration(session, pipeline_id: str, json_configuration: str):
    node_uuid = uuid.uuid4()
    json_configuration = json_configuration.replace("SIMCORE_NODE_UUID", str(node_uuid))
    configuration = json.loads(json_configuration)

    new_Node = ComputationalTask(pipeline_id=pipeline_id, node_id=node_uuid, schema=configuration["schema"], inputs=configuration["inputs"], outputs=configuration["outputs"])
    session.add(new_Node)
    session.commit()    
    return node_uuid

@pytest.fixture
def here()->Path:
    return Path(__file__).parent

@pytest.fixture
def test_configuration_file(here):
    return here / "config" / "default_config.json"

@pytest.fixture
def empty_configuration_file(here):
    return here / "config" / "empty_config.json"

@pytest.fixture()
def default_nodeports_configuration(engine, session, test_configuration_file):
    # prepare database with default configuration
    json_configuration = test_configuration_file.read_text()
    
    pipeline_id = _create_new_pipeline(engine, session)
    node_uuid = _set_configuration(session, pipeline_id, json_configuration)
    os.environ["SIMCORE_NODE_UUID"]=str(node_uuid)
    return engine, session, pipeline_id, node_uuid


def assign_config(config_dict:dict, port_type:str, entries: List[Tuple[str, str, Any]]):
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

@pytest.fixture()
def special_configuration(engine, session, empty_configuration_file: Path):
    def create_config(inputs: List[Tuple[str, str, Any]] =None, outputs: List[Tuple[str, str, Any]] =None):
        config_dict = json.loads(empty_configuration_file.read_text())
        assign_config(config_dict, "inputs", inputs)
        assign_config(config_dict, "outputs", outputs)

        pipeline_id = _create_new_pipeline(engine, session)
        node_uuid = _set_configuration(session, pipeline_id, json.dumps(config_dict))
        os.environ["SIMCORE_NODE_UUID"]=str(node_uuid)
        return config_dict, pipeline_id, node_uuid
    yield create_config

@pytest.fixture()
def special_2nodes_configuration(engine, session, empty_configuration_file: Path):
    def create_config(prev_node_inputs: List[Tuple[str, str, Any]] =None, prev_node_outputs: List[Tuple[str, str, Any]] =None,
                    inputs: List[Tuple[str, str, Any]] =None, outputs: List[Tuple[str, str, Any]] =None):
        pipeline_id = _create_new_pipeline(engine, session)

        # create previous node
        previous_config_dict = json.loads(empty_configuration_file.read_text())
        assign_config(previous_config_dict, "inputs", prev_node_inputs)
        assign_config(previous_config_dict, "outputs", prev_node_outputs)
        previous_node_uuid = _set_configuration(session, pipeline_id, json.dumps(previous_config_dict))

        # create current node
        config_dict = json.loads(empty_configuration_file.read_text())
        assign_config(config_dict, "inputs", inputs)
        assign_config(config_dict, "outputs", outputs)
        # configure links if necessary
        str_config = json.dumps(config_dict)
        str_config = str_config.replace("TEST_NODE_UUID", str(previous_node_uuid))
        config_dict = json.loads(str_config)
        node_uuid = _set_configuration(session, pipeline_id, str_config)
        # set env
        os.environ["SIMCORE_NODE_UUID"]=str(node_uuid)
        return config_dict, pipeline_id, node_uuid
    yield create_config

@pytest.fixture()
def special_nodeports_configuration(engine, session):
    def create_special_config(node_configuration: dict, other_node_configurations: list = []):  # pylint: disable=dangerous-default-value
        pipeline_id = _create_new_pipeline(engine, session)
        # configure current node
        node_uuid = _set_configuration(session, pipeline_id, json.dumps(node_configuration))
        os.environ["SIMCORE_NODE_UUID"]=str(node_uuid)
        # add other nodes
        other_node_uuids = []
        for other_node_config in other_node_configurations:
            other_node_uuids.append(_set_configuration(session, pipeline_id, json.dumps(other_node_config)))
        return engine, session, pipeline_id, node_uuid, other_node_uuids
        
    return create_special_config

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
