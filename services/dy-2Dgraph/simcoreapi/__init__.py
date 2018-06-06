#pylint: disable=C0111
#pylint: disable=C0103
import os
from simcoreapi import simcore 
from simcoreapi import config
from simcoreapi import exceptions

import simcoreapi.serialization

CONFIG = config.CONFIG[os.environ.get("simcoreapi_CONFIG", "default")]
# create initial Simcore object
PORTS = simcoreapi.serialization.create_from_json(CONFIG.get_ports_configuration, CONFIG.write_ports_configuration, auto_update=True)
