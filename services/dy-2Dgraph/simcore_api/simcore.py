"""
This class allow the client to access the inputs and outputs assigned to the node.

Example:
    $ import Simcore
    $ Simcore.input1.type

"""
import json
from datetime import datetime
import dateutil.parser

from simcore_api import config

class Simcore(object):
    __timestamp = datetime.utcnow()
    __initializing = True
    def __init__(self, definition):
        print("initiliasiing Simcore with ", definition)
        self.__initializing = True
        if "timestamp" in definition:
            # convert to a datetime object
            definition["timestamp"] = dateutil.parser.parse(definition["timestamp"])
        vars(self).update(definition)
        self.__initializing = False

    def __getattribute__(self, attr):
        print("get attribute called with ", attr)
        if attr == "__dict__" or attr == "__class__" or attr == "__iter__" or attr == "_Simcore__initializing" or attr == "timestamp":
            return object.__getattribute__(self, attr)    
        # is anything new?
        if not Simcore.__validate_connection_configuration(self.timestamp):
            print("updating the interface for attr ", attr)
            # we need to update the interface
            updated_simcore = Simcore.create()
            # self.__setattr__()
            vars(self).clear()
            vars(self).update(vars(updated_simcore))

        return object.__getattribute__(self, attr)
            

    @staticmethod
    def create():
        json_data = config.get_connection_configuration()
        if "simcore" not in json_data or "timestamp" not in json_data:
            raise Exception("invalid simcore data")

        simcore = json.loads(json.dumps(json_data["simcore"]), object_hook=Simcore)
        simcore.timestamp = dateutil.parser.parse(json_data["timestamp"])
        return simcore

    @staticmethod
    def __validate_connection_configuration(timestamp):
        connection_config = config.get_connection_configuration()
        return timestamp >= dateutil.parser.parse(connection_config["timestamp"])