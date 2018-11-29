 #pylint: disable=W0621, unused-argument, too-many-arguments
import json
import uuid
from pathlib import Path
from typing import Any, List, Tuple

import pytest
import yarl
from helpers import helpers
from simcore_sdk.models.pipeline_models import (Base, ComputationalPipeline,
                                                ComputationalTask)
from simcore_sdk.node_ports import node_config



@pytest.fixture
def user_id()->int:
    # see fixtures/postgres.py
    yield 1258

@pytest.fixture
def s3_simcore_location() ->str:
    yield helpers.SIMCORE_STORE

@pytest.fixture
def filemanager_cfg(storage, user_id, bucket):
    storage_endpoint = yarl.URL(storage)
    node_config.STORAGE_ENDPOINT = "{}:{}".format(storage_endpoint.host, storage_endpoint.port)
    node_config.USER_ID = user_id
    node_config.BUCKET = bucket
    yield

@pytest.fixture
def project_id()->str:
    return str(uuid.uuid4())

@pytest.fixture
def node_uuid()->str:
    return str(uuid.uuid4())

@pytest.fixture
def file_uuid(project_id, node_uuid)->str:
    def create(file_path:Path, project:str=None, node:str=None):
        if project is None:
            project = project_id
        if node is None:
            node = node_uuid
        return helpers.file_uuid(file_path, project, node)
    yield create

@pytest.fixture(scope='session')
def here()->Path:
    yield Path(__file__).parent

@pytest.fixture(scope='session')
def docker_compose_file(bucket, pytestconfig, here): # pylint:disable=unused-argument
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
def default_configuration(postgres, default_configuration_file, project_id, node_uuid):
    # prepare database with default configuration
    json_configuration = default_configuration_file.read_text()

    _create_new_pipeline(postgres, project_id)
    _set_configuration(postgres, project_id, node_uuid, json_configuration)
    config_dict = json.loads(json_configuration)
    node_config.NODE_UUID = str(node_uuid)
    node_config.PROJECT_ID = str(project_id)
    yield config_dict
    # teardown
    postgres.query(ComputationalTask).delete()
    postgres.query(ComputationalPipeline).delete()
    postgres.commit()

@pytest.fixture()
def node_link():
    def create_node_link(key:str):
        return {"nodeUuid":"TEST_NODE_UUID", "output":key}
    yield create_node_link

@pytest.fixture()
def store_link(s3_client, bucket, file_uuid, s3_simcore_location):
    def create_store_link(file_path:Path, project_id:str=None, node_id:str=None):
        # upload the file to S3
        assert Path(file_path).exists()
        file_id = file_uuid(file_path, project_id, node_id)
        # using the s3 client the path must be adapted
        #TODO: use the storage sdk instead
        s3_object = Path(project_id, node_id, Path(file_path).name).as_posix()
        s3_client.upload_file(bucket, s3_object, str(file_path))
        return {"store":s3_simcore_location, "path":file_id}
    yield create_store_link

@pytest.fixture(scope="function")
def special_configuration(postgres, empty_configuration_file: Path, project_id, node_uuid):
    def create_config(inputs: List[Tuple[str, str, Any]] =None, outputs: List[Tuple[str, str, Any]] =None, project_id:str =project_id, node_id:str = node_uuid):
        config_dict = json.loads(empty_configuration_file.read_text())
        _assign_config(config_dict, "inputs", inputs)
        _assign_config(config_dict, "outputs", outputs)
        project_id = _create_new_pipeline(postgres, project_id)
        node_uuid = _set_configuration(postgres, project_id, node_id, json.dumps(config_dict))
        node_config.NODE_UUID = str(node_uuid)
        node_config.PROJECT_ID = str(project_id)
        return config_dict, project_id, node_uuid
    yield create_config
    # teardown
    postgres.query(ComputationalTask).delete()
    postgres.query(ComputationalPipeline).delete()
    postgres.commit()

@pytest.fixture(scope="function")
def special_2nodes_configuration(postgres, empty_configuration_file: Path, project_id, node_uuid):
    def create_config(prev_node_inputs: List[Tuple[str, str, Any]] =None, prev_node_outputs: List[Tuple[str, str, Any]] =None,
                    inputs: List[Tuple[str, str, Any]] =None, outputs: List[Tuple[str, str, Any]] =None,
                    project_id:str =project_id, previous_node_id:str = node_uuid, node_id:str = "asdasdadsa"):
        _create_new_pipeline(postgres, project_id)

        # create previous node
        previous_config_dict = json.loads(empty_configuration_file.read_text())
        _assign_config(previous_config_dict, "inputs", prev_node_inputs)
        _assign_config(previous_config_dict, "outputs", prev_node_outputs)
        previous_node_uuid = _set_configuration(postgres, project_id, previous_node_id, json.dumps(previous_config_dict))

        # create current node
        config_dict = json.loads(empty_configuration_file.read_text())
        _assign_config(config_dict, "inputs", inputs)
        _assign_config(config_dict, "outputs", outputs)
        # configure links if necessary
        str_config = json.dumps(config_dict)
        str_config = str_config.replace("TEST_NODE_UUID", str(previous_node_uuid))
        config_dict = json.loads(str_config)
        node_uuid = _set_configuration(postgres, project_id, node_id, str_config)
        node_config.NODE_UUID = str(node_uuid)
        node_config.PROJECT_ID = str(project_id)
        return config_dict, project_id, node_uuid
    yield create_config
    # teardown
    postgres.query(ComputationalTask).delete()
    postgres.query(ComputationalPipeline).delete()
    postgres.commit()

def _create_new_pipeline(session, project:str)->str:
    new_Pipeline = ComputationalPipeline(project_id=project)
    session.add(new_Pipeline)
    session.commit()
    return new_Pipeline.project_id

def _set_configuration(session, project_id: str, node_id:str, json_configuration: str):
    node_uuid = node_id
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
