"""this module allows to get the data to import from the connected previous nodes and to set the
    data going to following nodes.
"""
import logging
from simcore_api import exceptions
from simcore_api import serialization
from simcore_api._itemslist import DataItemsList


_LOGGER = logging.getLogger(__name__)

#pylint: disable=C0111
class Simcore(object):
    """This class allow the client to access the inputs and outputs assigned to the node."""
    _version = "0.1"
    def __init__(self, version, inputs=None, outputs=None):
        _LOGGER.debug("Initialising Simcore object with version %s, inputs %s and outputs %s", version, inputs, outputs)
        if self._version != version:
            raise exceptions.WrongProtocolVersionError(self._version, version)
        
        # inputs are per definition read-only
        if inputs is None:
            inputs = DataItemsList()
        self.__inputs = inputs
        self.__inputs.read_only = True

        # outputs are currently read-only as we do not allow dynamic change of
        # number of outputs or changing their type or so for now.
        if outputs is None:
            outputs = DataItemsList()
        self.__outputs = outputs
        self.__outputs.read_only = True
        self.__outputs.change_notifier = self.save_to_json

        self.__json_reader = None
        self.__json_writer = None
        self.autoupdate = False
        _LOGGER.debug("Initialised Simcore object with version %s, inputs %s and outputs %s", version, inputs, outputs)
        
    @property
    def inputs(self):
        _LOGGER.debug("Getting inputs with autoupdate: %s", self.autoupdate)
        if self.autoupdate:                        
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
        _LOGGER.debug("Getting outputs with autoupdate: %s", self.autoupdate)
        if self.autoupdate:
            self.update_from_json()
        return self.__outputs

    @outputs.setter
    def outputs(self, value):
        # this is forbidden        
        _LOGGER.debug("Setting outputs with %s", value)
        raise exceptions.ReadOnlyError(self.__outputs)
        #self.__outputs = value

    @property
    def json_reader(self):
        _LOGGER.debug("Getting json configuration")
        return self.__json_reader

    @json_reader.setter
    def json_reader(self, value):
        _LOGGER.debug("Setting json configuration with %s", value)
        self.__json_reader = value
    
    @property
    def json_writer(self):
        _LOGGER.debug("Getting json writer")
        return self.__json_writer

    @json_writer.setter
    def json_writer(self, value):
        _LOGGER.debug("Setting json writer with %s", value)
        self.__json_writer = value

    def update_from_json(self):
        _LOGGER.debug("Updating json configuration")
        change_notifier = self.__outputs.change_notifier
        updated_simcore = serialization.create_from_json(self.json_reader)        
        self.__inputs = updated_simcore.inputs
        self.__outputs = updated_simcore.outputs
        self.__outputs.change_notifier = change_notifier
        _LOGGER.debug("Updated json configuration")
    
    def save_to_json(self):
        _LOGGER.info("Saving Simcore object to json")
        serialization.save_to_json(self)
