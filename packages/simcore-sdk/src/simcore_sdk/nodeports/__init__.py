#pylint: disable=C0111
#pylint: disable=C0103
import os
from simcore_sdk.nodeports import config
from simcore_sdk.nodeports import io
from simcore_sdk.nodeports import serialization

_CONFIG = config.CONFIG[os.environ.get("simcoreapi_CONFIG", "default")]
_IO = io.IO(config=_CONFIG)
# create initial Simcore object
PORTS = serialization.create_from_json(_IO.get_ports_configuration, _IO.write_ports_configuration, auto_update=True)
