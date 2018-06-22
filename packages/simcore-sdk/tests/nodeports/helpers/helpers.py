#pylint: disable=C0111

from sqlalchemy.orm.attributes import flag_modified
from simcore_sdk.models.pipeline_models import ComputationalTask

def update_configuration(session, pipeline_id, node_uuid, new_configuration):
    task = session.query(ComputationalTask).filter(ComputationalTask.pipeline_id==str(pipeline_id), ComputationalTask.node_id==str(node_uuid)).one()
    task.input = new_configuration["inputs"]
    flag_modified(task, "input")
    task.output = new_configuration["outputs"]
    flag_modified(task, "output")
    session.commit()
    

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
