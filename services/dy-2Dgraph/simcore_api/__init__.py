#pylint: disable=C0111
#pylint: disable=C0103
import simcore_api.config
from simcore_api.simcore import Simcore

simcore = Simcore.create_from_json(simcore_api.config.get_ports_configuration)
