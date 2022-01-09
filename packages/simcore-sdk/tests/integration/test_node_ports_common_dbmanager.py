# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import json
from pathlib import Path
from typing import Callable, Dict

from simcore_sdk.node_ports_common.dbmanager import DBManager

pytest_simcore_core_services_selection = [
    "migration",
    "postgres",
]

pytest_simcore_ops_services_selection = ["minio"]


async def test_db_manager_read_config(
    project_id: str,
    node_uuid: str,
    node_ports_config: None,
    default_configuration: Dict,
):
    db_manager = DBManager()
    ports_configuration_str = await db_manager.get_ports_configuration_from_node_uuid(
        project_id, node_uuid
    )

    loaded_config_specs = json.loads(ports_configuration_str)
    assert loaded_config_specs == default_configuration


async def test_db_manager_write_config(
    project_id: str,
    node_uuid: str,
    node_ports_config: None,
    special_configuration: Callable,
    default_configuration_file: Path,
):
    # create an empty config
    special_configuration()
    # read the default config
    json_configuration = default_configuration_file.read_text()
    # write the default config to the database
    db_manager = DBManager()
    await db_manager.write_ports_configuration(
        json_configuration, project_id, node_uuid
    )

    ports_configuration_str = await db_manager.get_ports_configuration_from_node_uuid(
        project_id, node_uuid
    )
    assert json.loads(ports_configuration_str) == json.loads(json_configuration)
