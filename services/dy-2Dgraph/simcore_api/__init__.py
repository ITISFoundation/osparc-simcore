import os
from simcore_api.simcore import Simcore

config_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), r"../config/connection_config.json")

simcore =  Simcore.create_from_json_file(config_path)
