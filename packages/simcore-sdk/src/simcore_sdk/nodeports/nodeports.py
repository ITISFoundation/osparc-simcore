"""this module allows to get the data to import from the connected previous nodes and to set the
    data going to following nodes.
"""
import logging
from simcore_sdk.nodeports import exceptions, dbmanager, serialization
from simcore_sdk.nodeports._itemslist import DataItemsList


_LOGGER = logging.getLogger(__name__)

#pylint: disable=C0111
class Nodeports:
    """This class allow the client to access the inputs and outputs assigned to the node."""
    _version = "0.1"
    def __init__(self, version, inputs=None, outputs=None):
        _LOGGER.debug("Initialising Nodeports object with version %s, inputs %s and outputs %s", version, inputs, outputs)
        if self._version != version:
            raise exceptions.WrongProtocolVersionError(self._version, version)
        
        # inputs are per definition read-only
        if inputs is None:
            inputs = DataItemsList()
        self.__inputs = inputs
        self.__inputs.read_only = True
        self.__inputs.get_node_from_node_uuid_cb = self.get_node_from_node_uuid

        # outputs are currently read-only as we do not allow dynamic change of
        # number of outputs or changing their type or so for now.
        if outputs is None:
            outputs = DataItemsList()
        self.__outputs = outputs
        self.__outputs.read_only = True
        self.__outputs.change_notifier = self.save_to_json
        self.__outputs.get_node_from_node_uuid_cb = self.get_node_from_node_uuid

        self.db_mgr = None
        self.autoread = False
        self.autowrite = False
        
        _LOGGER.debug("Initialised Nodeports object with version %s, inputs %s and outputs %s", version, inputs, outputs)
        
    @property
    def inputs(self):
        _LOGGER.debug("Getting inputs with autoread: %s", self.autoread)
        if self.autoread:                        
            self.update_from_json()
        return self.__inputs

    @inputs.setter
    def inputs(self, value):
        # this is forbidden        
        _LOGGER.debug("Setting inputs with %s", value)
        raise exceptions.ReadOnlyError(self.__inputs)
        #self.__inputs = value
        
    @property
    def outputs(self):
        _LOGGER.debug("Getting outputs with autoread: %s", self.autoread)
        if self.autoread:
            self.update_from_json()
        return self.__outputs

    @outputs.setter
    def outputs(self, value):
        # this is forbidden        
        _LOGGER.debug("Setting outputs with %s", value)
        raise exceptions.ReadOnlyError(self.__outputs)
        #self.__outputs = value

    def get(self, item_key):
        try:
            return self.inputs[item_key].get()
        except exceptions.UnboundPortError:
            # not available try outputs
            pass
        # if this fails it will raise an exception
        return self.outputs[item_key].get()


    def update_from_json(self):
        _LOGGER.debug("Updating json configuration")
        if not self.db_mgr:
            raise exceptions.NodeportsException("db manager is not initialised")
        change_notifier = self.__outputs.change_notifier
        updated_nodeports = serialization.create_from_json(self.db_mgr)        
        self.__inputs = updated_nodeports.inputs
        self.__outputs = updated_nodeports.outputs
        self.__outputs.change_notifier = change_notifier        
        _LOGGER.debug("Updated json configuration")
    
    def save_to_json(self):
        _LOGGER.info("Saving Nodeports object to json")
        serialization.save_to_json(self)

    def get_node_from_node_uuid(self, node_uuid):
        if not self.db_mgr:
            raise exceptions.NodeportsException("db manager is not initialised")
        return serialization.create_nodeports_from_uuid(self.db_mgr, node_uuid)


_db_manager = dbmanager.DBManager()
# create initial Simcore object
PORTS = serialization.create_from_json(_db_manager, auto_read=True, auto_write=True)