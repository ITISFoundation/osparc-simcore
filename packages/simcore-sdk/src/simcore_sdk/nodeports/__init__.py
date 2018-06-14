#pylint: disable=C0111
#pylint: disable=C0103
import os
from simcore_sdk.nodeports import config
from simcore_sdk.nodeports import serialization

CONFIG = config.CONFIG[os.environ.get("simcoreapi_CONFIG", "default")]
# create initial Simcore object
PORTS = serialization.create_from_json(CONFIG.get_ports_configuration, CONFIG.write_ports_configuration, auto_update=True)
