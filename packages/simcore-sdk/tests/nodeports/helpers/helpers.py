#pylint: disable=C0111
import logging
from simcore_sdk.models.pipeline_models import ComputationalTask

log = logging.getLogger(__name__)

def update_configuration(session, pipeline_id, node_uuid, new_configuration):
    log.debug("Update configuration of pipeline %s, node %s, on session %s", pipeline_id, node_uuid, session)
    task = session.query(ComputationalTask).filter(ComputationalTask.pipeline_id==str(pipeline_id), ComputationalTask.node_id==str(node_uuid))
    task.update(dict(input=new_configuration["inputs"], output=new_configuration["outputs"]))
    session.commit()
    log.debug("Updated configuration")


def update_config_file(path, config):
    import json
    with open(path, "w") as json_file:
        json.dump(config, json_file)


def get_empty_config():
    return {
        "version": "0.1",
        "inputs": [
        ],
        "outputs": [
        ]
    }
