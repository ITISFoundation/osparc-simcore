#pylint: disable=C0111
import json
import logging
import uuid
from pathlib import Path

from simcore_sdk.models.pipeline_models import ComputationalTask

log = logging.getLogger(__name__)

def update_configuration(session, project_id, node_uuid, new_configuration):
    log.debug("Update configuration of pipeline %s, node %s, on session %s", project_id, node_uuid, session)
    task = session.query(ComputationalTask).filter(ComputationalTask.project_id==str(project_id), ComputationalTask.node_id==str(node_uuid))
    task.update(dict(schema=new_configuration["schema"], inputs=new_configuration["inputs"], outputs=new_configuration["outputs"]))
    session.commit()
    log.debug("Updated configuration")


def update_config_file(path, config):
    
    with open(path, "w") as json_file:
        json.dump(config, json_file)


def get_empty_config():
    return {
        "version": "0.1",
        "schema": {"inputs":{}, "outputs":{}},
        "inputs": {},
        "outputs": {}
    }


SIMCORE_STORE = "simcore.s3"

def file_uuid(store:str, bucket:str, file_path:Path):
    project = uuid.uuid4()
    node = uuid.uuid4()
    file_id = "{}/{}/{}/{}/{}".format(store, bucket, project, node, Path(file_path).name)
    return file_id
