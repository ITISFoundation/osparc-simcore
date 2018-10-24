import json
import os
import sys
import uuid

import pytest

from simcore_sdk.models.pipeline_models import (Base, ComputationalPipeline,
                                                ComputationalTask)


sys.path.append(os.path.join(os.path.dirname(__file__), "helpers"))

pytest_plugins = ["tests.fixtures.postgres", "tests.fixtures.minio-fix"]

@pytest.fixture(scope='session')
def docker_compose_file(pytestconfig): # pylint:disable=unused-argument
    my_path = os.path.join(os.path.dirname(__file__), 'docker-compose.yml')
    return my_path


def _create_new_pipeline(engine, session):
    # prepare database with default configuration
    Base.metadata.create_all(engine)
    new_Pipeline = ComputationalPipeline()
    session.add(new_Pipeline)
    session.commit()

    os.environ["SIMCORE_PIPELINE_ID"]=str(new_Pipeline.pipeline_id)

    return new_Pipeline.pipeline_id

def _set_configuration(session, pipeline_id, json_configuration: str):
    node_uuid = uuid.uuid4()
    json_configuration = json_configuration.replace("SIMCORE_NODE_UUID", str(node_uuid))
    configuration = json.loads(json_configuration)

    new_Node = ComputationalTask(pipeline_id=pipeline_id, node_id=node_uuid, input=configuration["inputs"], output=configuration["outputs"])
    session.add(new_Node)
    session.commit()    
    return node_uuid

@pytest.fixture()
def default_nodeports_configuration(engine, session):
    """initialise nodeports with default configuration file
    """
    # prepare database with default configuration
    default_config_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), r"connection_config.json")
    with open(default_config_path) as config_file:
        json_configuration = config_file.read()
    
    pipeline_id = _create_new_pipeline(engine, session)
    node_uuid = _set_configuration(session, pipeline_id, json_configuration)
    os.environ["SIMCORE_NODE_UUID"]=str(node_uuid)
    return engine, session, pipeline_id, node_uuid

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