import os
import logging

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import exc
from sqlalchemy.orm.attributes import flag_modified

from simcore_sdk.config.db import Config as db_config
from simcore_sdk.models.pipeline_models import ComputationalTask as NodeModel
from simcore_sdk.nodeports import serialization
from simcore_sdk.nodeports.config import Location

_LOGGER = logging.getLogger(__name__)

class DbSettings(object):
    def __init__(self):
        self._db_config = db_config()
        self.db = create_engine(self._db_config.endpoint, client_encoding='utf8')
        self.Session = sessionmaker(self.db)
        self.session = self.Session()

class IO(object):
    def __init__(self, config):
        if config.LOCATION == Location.DATABASE:            
            self._db = DbSettings()            

        self.config = config

    def __get_configuration_from_file(self):
        file_location = os.environ.get('SIMCORE_CONFIG_PATH', self.config.DEFAULT_FILE_LOCATION)
        config_file = os.path.join(os.path.dirname(os.path.realpath(__file__)), file_location)
        _LOGGER.debug("Reading ports configuration from %s", config_file)
        with open(config_file) as simcore_config:
            return simcore_config.read()

    def __get_node_from_db(self, node_uuid):        
        pipeline_id = os.environ.get('PIPELINE_NODE_ID')
        _LOGGER.debug("Reading from database for pipeline id %s and node id %s", pipeline_id, node_uuid)
        try:
            return self._db.session.query(NodeModel).filter(NodeModel.pipeline_id==pipeline_id, NodeModel.node_id==node_uuid).one()                
        except exc.NoResultFound:
            _LOGGER.exception("the node id %s was not found", node_uuid)
        except exc.MultipleResultsFound:
            _LOGGER.exception("the node id %s is not unique", node_uuid)

    def __get_configuration_from_db(self, node_uuid=None):        
        _LOGGER.debug("Reading from database")        
        node = self.__get_node_from_db(node_uuid)
        node_json_config = serialization.save_node_to_json(node)
        _LOGGER.debug("Found and converted to json")
        return node_json_config

    def get_ports_configuration(self):
        """returns the json configuration of the node ports where this code is running. 
        
        Returns:
            string -- a json containing the ports configuration                
        """
        _LOGGER.debug("Getting ports configuration using %s", self.config.LOCATION)
        if self.config.LOCATION == Location.FILE:
            return self.__get_configuration_from_file()
        return self.__get_configuration_from_db(node_uuid=os.environ.get('SIMCORE_NODE_UUID'))

    def get_ports_configuration_from_node_uuid(self, node_uuid):
        """returns the json configuration of a node with a specific node uuid in the same pipeline
        
        Arguments:
            node_uuid {string} -- node uuid
        
        Returns:
            string -- a json containing the ports configuration
        """
        _LOGGER.debug("Getting ports configuration of node %s using %s", node_uuid, self.config.LOCATION)
        if self.config.LOCATION == Location.FILE:
            raise NotImplementedError
        return self.__get_configuration_from_db(node_uuid=node_uuid)

    def __write_configuration_to_file(self, json_configuration):
        file_location = os.environ.get('SIMCORE_CONFIG_PATH', self.config.DEFAULT_FILE_LOCATION)
        config_file = os.path.join(os.path.dirname(os.path.realpath(__file__)), file_location)
        _LOGGER.debug("Writing ports configuration to %s", config_file)
        with open(config_file, "w") as simcore_file:
            simcore_file.write(json_configuration)

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
        _LOGGER.debug("Writing ports configuration to %s", self.config.LOCATION)
        if self.config.LOCATION == Location.FILE:
            self.__write_configuration_to_file(json_configuration)
        else:
            self.__write_configuration_to_db(json_configuration)



# def create_dummy():
#     inputs = [
#         dict(
#             key="in_1",
#             label="computational data",
#             description="these are computed data out of a pipeline",
#             type="file-url",
#             value="/home/jovyan/data/outputControllerOut.dat",
#             timestamp="2018-05-23T15:34:53.511Z"
#         ),
#         dict(
#             key="in_5",
#             label="some number",
#             description="numbering things",
#             type="int",
#             value="666",
#             timestamp="2018-05-23T15:34:53.511Z"
#         )
#         ]
#     outputs = []
#     new_Node = NodeModel(pipeline_id=pipeline_id node_id=node_id, tag="0.1", inputs=inputs, outputs=outputs)
#     self._db.session.add(new_Node)
#     self._db.session.commit()
#create_dummy()
#return