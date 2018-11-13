import json
import logging

from sqlalchemy import create_engine
from sqlalchemy.orm import exc, sessionmaker
from sqlalchemy.orm.attributes import flag_modified

from simcore_sdk.config.db import Config as db_config
from simcore_sdk.models.pipeline_models import ComputationalTask as NodeModel

from . import config

log = logging.getLogger(__name__)

class DbSettings:
    def __init__(self):
        self._db_config = db_config()
        self.db = create_engine(self._db_config.endpoint, client_encoding='utf8')
        self.Session = sessionmaker(self.db)
        self.session = self.Session()

def save_node_to_json(node):
    node_json_config = json.dumps(node, cls=_NodeModelEncoder)
    return node_json_config

def create_node_from_json(json_config):
    node_configuration = json.loads(json_config)
    node = NodeModel(schema=node_configuration["schema"], inputs=node_configuration["inputs"], outputs=node_configuration["outputs"])
    return node

class _NodeModelEncoder(json.JSONEncoder):
    def default(self, o): # pylint: disable=E0202
        log.debug("Encoding object: %s", o)
        if isinstance(o, NodeModel):
            log.debug("Encoding Node object")
            return {
                    "version": "0.1",
                    "schema": o.schema,
                    "inputs": o.inputs,
                    "outputs": o.outputs
                    }
            
        log.debug("Encoding object using defaults")
        return json.JSONEncoder.default(self, o)

class DBManager:
    def __init__(self):
        self._db = DbSettings()        
        node = self._db.session.query(NodeModel).filter(NodeModel.node_id == config.NODE_UUID).one()
        config.PROJECT_ID = node.project_id

    def __get_node_from_db(self, node_uuid):
        log.debug("Reading from database for node uuid %s", node_uuid)
        try:
            return self._db.session.query(NodeModel).filter(NodeModel.node_id == node_uuid).one()
        except exc.NoResultFound:
            log.exception("the node id %s was not found", node_uuid)
        except exc.MultipleResultsFound:
            log.exception("the node id %s is not unique", node_uuid)

    def __get_configuration_from_db(self, node_uuid=None):
        log.debug("Reading from database")
        node = self.__get_node_from_db(node_uuid)
        node_json_config = save_node_to_json(node)
        log.debug("Found and converted to json")
        return node_json_config

    def __write_configuration_to_db(self, json_configuration):
        log.debug("Writing to database")

        updated_node = create_node_from_json(json_configuration)
        node = self.__get_node_from_db(node_uuid=config.NODE_UUID)

        if node.schema != updated_node.schema:
            node.schema = updated_node.schema
            flag_modified(node, "schema")
        if node.inputs != updated_node.inputs:
            node.inputs = updated_node.inputs
            flag_modified(node, "inputs")
        if node.outputs != updated_node.outputs:
            node.outputs = updated_node.outputs
            flag_modified(node, "outputs")

        # node.inputs = updated_node.inputs
        # node.outputs = updated_node.outputs
        self._db.session.commit()

    def write_ports_configuration(self, json_configuration):
        """writes the json configuration of the node ports.
        """
        log.debug("Writing ports configuration")
        self.__write_configuration_to_db(json_configuration)

    def get_ports_configuration(self):
        """returns the json configuration of the node ports where this code is running.

        Returns:
            string -- a json containing the ports configuration
        """
        log.debug("Getting ports configuration")
        return self.__get_configuration_from_db(node_uuid=config.NODE_UUID)

    def get_ports_configuration_from_node_uuid(self, node_uuid):
        """returns the json configuration of a node with a specific node uuid in the same pipeline

        Arguments:
            node_uuid {string} -- node uuid

        Returns:
            string -- a json containing the ports configuration
        """
        log.debug("Getting ports configuration of node %s", node_uuid)
        return self.__get_configuration_from_db(node_uuid=node_uuid)
