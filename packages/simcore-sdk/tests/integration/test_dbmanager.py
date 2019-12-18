# pylint:disable=wildcard-import
# pylint:disable=unused-import
# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=too-many-arguments

import json

from simcore_sdk.node_ports import config
from simcore_sdk.node_ports.dbmanager import DBManager


core_services = [
    'postgres',
]

ops_services = [
#    'adminer'
]

def test_db_manager_read_config(default_configuration):
    config_dict = default_configuration
    db_manager = DBManager()
    ports_configuration_str = db_manager.get_ports_configuration_from_node_uuid(config.NODE_UUID)

    loaded_config_specs = json.loads(ports_configuration_str)
    assert loaded_config_specs == config_dict

def test_db_manager_write_config(special_configuration, default_configuration_file):
    # create an empty config
    special_configuration()
    # read the default config
    json_configuration = default_configuration_file.read_text()
    # write the default config to the database
    db_manager = DBManager()
    db_manager.write_ports_configuration(json_configuration, config.NODE_UUID)

    ports_configuration_str = db_manager.get_ports_configuration_from_node_uuid(config.NODE_UUID)
    assert json.loads(ports_configuration_str) == json.loads(json_configuration)
