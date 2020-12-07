# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from typing import Any, Dict

import pytest
from simcore_sdk.node_ports.dbmanager import DBManager
from simcore_sdk.node_ports.exceptions import InvalidProtocolError
from simcore_sdk.node_ports_v2.serialization_v2 import (
    create_nodeports_from_db,
    save_nodeports_to_db,
)


@pytest.mark.parametrize("auto_update", [True, False])
async def test_create_nodeports_from_db(
    mock_db_manager,
    auto_update: bool,
    node_uuid: str,
    default_configuration: Dict[str, Any],
):
    db_manager: DBManager = mock_db_manager(default_configuration)
    node_ports = await create_nodeports_from_db(db_manager, node_uuid, auto_update)
    assert node_ports.db_manager == db_manager
    assert node_ports.node_uuid == node_uuid
    # pylint: disable=comparison-with-callable
    assert node_ports.save_to_db_cb == save_nodeports_to_db
    assert node_ports.node_port_creator_cb == create_nodeports_from_db
    assert node_ports.auto_update == auto_update


async def test_create_nodeports_from_db_with_invalid_cfg(
    mock_db_manager,
    node_uuid: str,
):
    invalid_config = {"bad_key": "bad_value"}
    db_manager: DBManager = mock_db_manager(invalid_config)
    with pytest.raises(InvalidProtocolError):
        _ = await create_nodeports_from_db(db_manager, node_uuid)


async def test_save_nodeports_to_db(
    mock_db_manager,
    node_uuid: str,
    default_configuration: Dict[str, Any],
):
    db_manager: DBManager = mock_db_manager(default_configuration)
    node_ports = await create_nodeports_from_db(db_manager, node_uuid)

    await save_nodeports_to_db(node_ports)
