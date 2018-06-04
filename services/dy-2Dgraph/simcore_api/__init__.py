#pylint: disable=C0111
#pylint: disable=C0103
import logging
import os
from simcore_api import simcore 
from simcore_api import config

CONFIG = config.CONFIG[os.environ.get("SIMCORE_API_CONFIG", "default")]
# create initial Simcore object
PORTS = simcore.Simcore.create_from_json(CONFIG.get_ports_configuration, CONFIG.write_ports_configuration)
