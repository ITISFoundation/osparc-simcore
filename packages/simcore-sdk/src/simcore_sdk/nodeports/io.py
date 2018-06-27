import os
import logging

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import exc
from sqlalchemy.orm.attributes import flag_modified

from simcore_sdk.config.db import Config as db_config
from simcore_sdk.models.pipeline_models import ComputationalTask as NodeModel
from simcore_sdk.nodeports import serialization

_LOGGER = logging.getLogger(__name__)

class DbSettings(object):
    def __init__(self):
        self._db_config = db_config()
        self.db = create_engine(self._db_config.endpoint, client_encoding='utf8')
        self.Session = sessionmaker(self.db)
        self.session = self.Session()

class IO(object):
    def __init__(self):
        self._db = DbSettings()            

    def __get_node_from_db(self, node_uuid):        
        _LOGGER.debug("Reading from database for node uuid %s", node_uuid)
        try:
            #TODO: SAN the call to first must be replaced by one() as soon as the pipeline ID issue is resolved
            return self._db.session.query(NodeModel).filter(NodeModel.node_id==node_uuid).first()                
        except exc.NoResultFound:
            _LOGGER.exception("the node id %s was not found", node_uuid)
        except exc.MultipleResultsFound:
            _LOGGER.exception("the node id %s is not unique", node_uuid)

    def __get_configuration_from_db(self, node_uuid=None, set_pipeline_id=False):        
        _LOGGER.debug("Reading from database")        
        node = self.__get_node_from_db(node_uuid)
        if set_pipeline_id:
            os.environ["SIMCORE_PIPELINE_ID"]=str(node.pipeline_id)
        node_json_config = serialization.save_node_to_json(node)
        _LOGGER.debug("Found and converted to json")
        return node_json_config

    def __write_configuration_to_db(self, json_configuration):
        _LOGGER.debug("Writing to database")

        updated_node = serialization.create_node_from_json(json_configuration)
        node = self.__get_node_from_db(node_uuid=os.environ.get('SIMCORE_NODE_UUID'))        
        
        if node.input != updated_node.input:
            node.input = updated_node.input
            flag_modified(node, "input")
        if node.output != updated_node.output:
            node.output = updated_node.output
            flag_modified(node, "output")

        # node.inputs = updated_node.inputs
        # node.outputs = updated_node.outputs
        self._db.session.commit()

    def write_ports_configuration(self, json_configuration):
        """writes the json configuration of the node ports.
        """
        _LOGGER.debug("Writing ports configuration")
        self.__write_configuration_to_db(json_configuration)

    def get_ports_configuration(self):
        """returns the json configuration of the node ports where this code is running. 
        
        Returns:
            string -- a json containing the ports configuration                
        """
        _LOGGER.debug("Getting ports configuration")
        return self.__get_configuration_from_db(node_uuid=os.environ.get('SIMCORE_NODE_UUID'), set_pipeline_id=True)

    def get_ports_configuration_from_node_uuid(self, node_uuid):
        """returns the json configuration of a node with a specific node uuid in the same pipeline
        
        Arguments:
            node_uuid {string} -- node uuid
        
        Returns:
            string -- a json containing the ports configuration
        """
        _LOGGER.debug("Getting ports configuration of node %s", node_uuid)
        return self.__get_configuration_from_db(node_uuid=node_uuid)