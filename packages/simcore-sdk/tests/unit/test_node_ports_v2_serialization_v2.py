# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from typing import Any, Dict

import pytest
from simcore_sdk.node_ports_v2 import DBManager, exceptions
from simcore_sdk.node_ports_v2.serialization_v2 import dump, load


@pytest.mark.parametrize("auto_update", [True, False])
async def test_load(
    mock_db_manager,
    auto_update: bool,
    user_id: int,
    project_id: str,
    node_uuid: str,
    default_configuration: Dict[str, Any],
):
    db_manager: DBManager = mock_db_manager(default_configuration)
    node_ports = await load(
        db_manager=db_manager,
        user_id=user_id,
        project_id=project_id,
        node_uuid=node_uuid,
        auto_update=auto_update,
    )
    assert node_ports.db_manager == db_manager
    assert node_ports.node_uuid == node_uuid
    # pylint: disable=comparison-with-callable
    assert node_ports.save_to_db_cb == dump
    assert node_ports.node_port_creator_cb == load
    assert node_ports.auto_update == auto_update


async def test_load_with_invalid_cfg(
    mock_db_manager,
    user_id: int,
    project_id: str,
    node_uuid: str,
):
    invalid_config = {"bad_key": "bad_value"}
    db_manager: DBManager = mock_db_manager(invalid_config)
    with pytest.raises(exceptions.InvalidProtocolError):
        _ = await load(
            db_manager=db_manager,
            user_id=user_id,
            project_id=project_id,
            node_uuid=node_uuid,
        )


async def test_dump(
    mock_db_manager,
    user_id: int,
    project_id: str,
    node_uuid: str,
    default_configuration: Dict[str, Any],
):
    db_manager: DBManager = mock_db_manager(default_configuration)
    node_ports = await load(
        db_manager=db_manager,
        user_id=user_id,
        project_id=project_id,
        node_uuid=node_uuid,
    )

    await dump(node_ports)
