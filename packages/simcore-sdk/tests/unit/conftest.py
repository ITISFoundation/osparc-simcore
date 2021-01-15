# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import asyncio
import json
from typing import Any, Callable, Dict
from uuid import uuid4

import pytest
from simcore_sdk.node_ports.dbmanager import DBManager


@pytest.fixture(scope="module")
def node_uuid() -> str:
    return str(uuid4())


@pytest.fixture(scope="function")
async def mock_db_manager(
    loop: asyncio.AbstractEventLoop,
    monkeypatch,
    node_uuid: str,
) -> Callable:
    def _mock_db_manager(port_cfg: Dict[str, Any]) -> DBManager:
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

        db_manager = DBManager()
        return db_manager

    yield _mock_db_manager
