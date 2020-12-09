import logging
import warnings

from . import config as node_config
from . import exceptions
from ._item import Item as Port
from .nodeports import ports

# nodeports is a library for accessing data linked to the node
# in that sense it should not log stuff unless the application code wants it to be so.
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())

warnings.warn(
    "node_ports is deprecated, use node_ports_v2 instead", category=DeprecationWarning
)
