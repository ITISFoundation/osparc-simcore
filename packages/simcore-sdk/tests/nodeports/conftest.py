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


def set_configuration(engine, session, json_configuration):
    node_uuid = uuid.uuid4()
    json_configuration = json_configuration.replace("SIMCORE_NODE_UUID", str(node_uuid))
    configuration = json.loads(json_configuration)

    # prepare database with default configuration
    Base.metadata.create_all(engine)
    new_Pipeline = ComputationalPipeline()
    session.add(new_Pipeline)
    session.commit()

    new_Node = ComputationalTask(pipeline_id=new_Pipeline.pipeline_id, node_id=node_uuid, input=configuration["inputs"], output=configuration["outputs"])
    session.add(new_Node)
    session.commit()    

    # set up access to database
    os.environ["SIMCORE_NODE_UUID"]=str(node_uuid)
    os.environ["SIMCORE_PIPELINE_ID"]=str(new_Pipeline.pipeline_id)    

    return engine, session, new_Pipeline.pipeline_id, node_uuid

@pytest.fixture()
def default_nodeports_configuration(engine, session):
    """initialise nodeports with default configuration file
    """
    # prepare database with default configuration
    default_config_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), r"connection_config.json")
    with open(default_config_path) as config_file:
        json_configuration = config_file.read()
    
    return set_configuration(engine, session, json_configuration)

@pytest.fixture()
def special_nodeports_configuration(engine, session):
    def create_special_config(configuration):
        return set_configuration(engine, session, json.dumps(configuration))
        
    return create_special_config
