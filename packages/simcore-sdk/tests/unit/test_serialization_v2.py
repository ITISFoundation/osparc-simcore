# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import asyncio
import json
from typing import Any, Dict
from uuid import uuid4

import pytest
from simcore_sdk.node_ports.dbmanager import DBManager
from simcore_sdk.node_ports.exceptions import InvalidProtocolError
from simcore_sdk.node_ports_v2.serialization_v2 import (
    create_nodeports_from_db,
    save_nodeports_to_db,
)
from sqlalchemy.exc import InvalidatePoolError


@pytest.fixture(scope="module")
def node_uuid() -> str:
    return str(uuid4())


@pytest.fixture(scope="function")
async def mock_db_manager(
    loop: asyncio.AbstractEventLoop,
    monkeypatch,
    node_uuid: str,
):
    def _mock_db_manager(port_cfg: Dict[str, Any]):
        async def mock_get_ports_configuration_from_node_uuid(*args, **kwargs) -> str:
            return json.dumps(port_cfg)

        async def mock_write_ports_configuration(
            self, json_configuration: str, uuid: str
        ):
            assert json.loads(json_configuration) == port_cfg
            assert uuid == node_uuid

        monkeypatch.setattr(
            DBManager,
            "get_ports_configuration_from_node_uuid",
            mock_get_ports_configuration_from_node_uuid,
        )
        monkeypatch.setattr(
            DBManager,
            "write_ports_configuration",
            mock_write_ports_configuration,
        )

    yield _mock_db_manager


@pytest.mark.parametrize("auto_update", [True, False])
async def test_create_nodeports_from_db(
    mock_db_manager,
    auto_update: bool,
    node_uuid: str,
    default_configuration: Dict[str, Any],
):
    mock_db_manager(default_configuration)
    db_manager = DBManager()
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
    mock_db_manager(invalid_config)
    db_manager = DBManager()
    with pytest.raises(InvalidProtocolError):
        node_ports = await create_nodeports_from_db(db_manager, node_uuid)


async def test_save_nodeports_to_db(
    mock_db_manager,
    node_uuid: str,
    default_configuration: Dict[str, Any],
):
    mock_db_manager(default_configuration)
    db_manager = DBManager()
    node_ports = await create_nodeports_from_db(db_manager, node_uuid)

    await save_nodeports_to_db(node_ports)
