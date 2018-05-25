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

    def __init__(self, definition):
        if "timestamp" in definition:
            # convert to a datetime object
            definition["timestamp"] = dateutil.parser.parse(definition["timestamp"])
        vars(self).update(definition)

    def __getattribute__(self, attr):
        if attr == "__dict__" or attr == "__class__" or attr == "__iter__" or attr == "timestamp":
            return object.__getattribute__(self, attr)    
        # is anything new?
        if not Simcore.__validate_connection_configuration(self.timestamp):
            # we need to update the interface
            updated_simcore = Simcore.create()
            vars(self).clear()
            vars(self).update(vars(updated_simcore))

        return object.__getattribute__(self, attr)
            

    @staticmethod
    def create():
        port_config = config.get_ports_configuration()
        if "timestamp" not in port_config:
            raise Exception("invalid simcore data")

        simcore = json.loads(json.dumps(port_config), object_hook=Simcore)        
        return simcore

    @staticmethod
    def __validate_connection_configuration(timestamp):
        connection_config = config.get_ports_configuration()
        return timestamp >= dateutil.parser.parse(connection_config["timestamp"])