# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import json
from collections.abc import AsyncIterator, Callable
from random import randint
from typing import Any
from uuid import uuid4

import pytest
from simcore_sdk.node_ports_common.dbmanager import DBManager


@pytest.fixture(scope="module")
def user_id() -> int:
    return randint(1, 10000)


@pytest.fixture(scope="module")
def project_id() -> str:
    return f"{uuid4()}"


@pytest.fixture(scope="module")
def node_uuid() -> str:
    return str(uuid4())


@pytest.fixture
async def mock_db_manager(
    monkeypatch,
    project_id: str,
    node_uuid: str,
) -> AsyncIterator[Callable]:
    def _mock_db_manager(port_cfg: dict[str, Any]) -> DBManager:
        async def mock_get_ports_configuration_from_node_uuid(*args, **kwargs) -> str:
            return json.dumps(port_cfg)

        async def mock_write_ports_configuration(
            self, json_configuration: str, p_id: str, n_id: str
        ):
            assert json.loads(json_configuration) == port_cfg
            assert p_id == project_id
            assert n_id == node_uuid

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

    return _mock_db_manager
