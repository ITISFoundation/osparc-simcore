#pylint: disable=C0111
#pylint: disable=C0103
import os
from simcore_api import simcore 
from simcore_api import config
from simcore_api import exceptions

import simcore_api.serialization

CONFIG = config.CONFIG[os.environ.get("SIMCORE_API_CONFIG", "default")]
# create initial Simcore object
PORTS = simcore_api.serialization.create_from_json(CONFIG.get_ports_configuration, CONFIG.write_ports_configuration, auto_update=True)
