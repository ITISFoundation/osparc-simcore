#pylint: disable=C0111
#pylint: disable=C0103
import logging
import os
import simcore_api.config
import simcore_api.simcore

CONFIG = simcore_api.config.CONFIG[os.environ.get("SIMCORE_API_CONFIG", "default")]
# create initial Simcore object
simcore = simcore_api.simcore.Simcore.create_from_json(CONFIG.get_ports_configuration)
