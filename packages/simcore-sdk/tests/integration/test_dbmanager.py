# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import asyncio
import json
from pathlib import Path
from typing import Callable, Dict

from simcore_sdk.node_ports import config
from simcore_sdk.node_ports.dbmanager import DBManager

core_services = [
    "postgres",
]

ops_services = []


async def test_db_manager_read_config(
    loop: asyncio.events.AbstractEventLoop,
    nodeports_config: None,
    default_configuration: Dict,
):
    db_manager = DBManager()
    ports_configuration_str = await db_manager.get_ports_configuration_from_node_uuid(
        config.NODE_UUID
    )

    loaded_config_specs = json.loads(ports_configuration_str)
    assert loaded_config_specs == default_configuration


async def test_db_manager_write_config(
    loop: asyncio.events.AbstractEventLoop,
    nodeports_config: None,
    special_configuration: Callable,
    default_configuration_file: Path,
):
    # create an empty config
    special_configuration()
    # read the default config
    json_configuration = default_configuration_file.read_text()
    # write the default config to the database
    db_manager = DBManager()
    await db_manager.write_ports_configuration(json_configuration, config.NODE_UUID)

    ports_configuration_str = await db_manager.get_ports_configuration_from_node_uuid(
        config.NODE_UUID
    )
    assert json.loads(ports_configuration_str) == json.loads(json_configuration)
