#pylint: disable=C0111
#pylint: disable=C0103
import logging
import simcore_api.config
from simcore_api.simcore import Simcore

# simcore_api is a library for accessing data linked to the node
# in that sense it should not log stuff unless the application code wants it to be so.
logging.getLogger(__name__).addHandler(logging.NullHandler())
# create initial Simcore object
simcore = Simcore.create_from_json(simcore_api.config.get_ports_configuration)
