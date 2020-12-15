# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from asyncio import Future
from pathlib import Path
from typing import Any, Callable, Dict

import pytest
from simcore_sdk.node_ports_v2 import Nodeports, exceptions, ports
from simcore_sdk.node_ports_v2.ports_mapping import InputsList, OutputsList
from utils_port_v2 import create_valid_port_mapping


@pytest.mark.parametrize(
    "auto_update",
    [
        pytest.param(True, id="Autoupdate enabled"),
        pytest.param(False, id="Autoupdate disabled"),
    ],
)
async def test_nodeports_auto_updates(
    mock_db_manager: Callable,
    default_configuration: Dict[str, Any],
    node_uuid: str,
    auto_update: bool,
):
    db_manager = mock_db_manager(default_configuration)

    original_inputs = create_valid_port_mapping(InputsList, suffix="original")
    original_outputs = create_valid_port_mapping(OutputsList, suffix="original")

    updated_inputs = create_valid_port_mapping(InputsList, suffix="updated")
    updated_outputs = create_valid_port_mapping(OutputsList, suffix="updated")

    async def mock_save_db_cb(*args, **kwargs):
        pass

    async def mock_node_port_creator_cb(*args, **kwargs):
        updated_node_ports = Nodeports(
            inputs=updated_inputs,
            outputs=updated_outputs,
            db_manager=db_manager,
            node_uuid=node_uuid,
            save_to_db_cb=mock_save_db_cb,
            node_port_creator_cb=mock_node_port_creator_cb,
            auto_update=False,
        )
        return updated_node_ports

    node_ports = Nodeports(
        inputs=original_inputs,
        outputs=original_outputs,
        db_manager=db_manager,
        node_uuid=node_uuid,
        save_to_db_cb=mock_save_db_cb,
        node_port_creator_cb=mock_node_port_creator_cb,
        auto_update=auto_update,
    )

    assert node_ports.internal_inputs == original_inputs
    assert node_ports.internal_outputs == original_outputs

    # this triggers an auto_update if auto_update is True
    node_inputs = await node_ports.inputs
    assert node_inputs == updated_inputs if auto_update else original_inputs
    node_outputs = await node_ports.outputs
    assert node_outputs == updated_outputs if auto_update else original_outputs


async def test_node_ports_accessors(
    mock_db_manager: Callable,
    default_configuration: Dict[str, Any],
    node_uuid: str,
):
    db_manager = mock_db_manager(default_configuration)

    original_inputs = create_valid_port_mapping(InputsList, suffix="original")
    original_outputs = create_valid_port_mapping(OutputsList, suffix="original")

    async def mock_save_db_cb(*args, **kwargs):
        pass

    async def mock_node_port_creator_cb(*args, **kwargs):
        updated_node_ports = Nodeports(
            inputs=original_inputs,
            outputs=original_outputs,
            db_manager=db_manager,
            node_uuid=node_uuid,
            save_to_db_cb=mock_save_db_cb,
            node_port_creator_cb=mock_node_port_creator_cb,
            auto_update=False,
        )
        return updated_node_ports

    node_ports = Nodeports(
        inputs=original_inputs,
        outputs=original_outputs,
        db_manager=db_manager,
        node_uuid=node_uuid,
        save_to_db_cb=mock_save_db_cb,
        node_port_creator_cb=mock_node_port_creator_cb,
        auto_update=False,
    )

    for port in original_inputs.values():
        assert await node_ports.get(port.key) == port.value
        await node_ports.set(port.key, port.value)

    with pytest.raises(exceptions.UnboundPortError):
        await node_ports.get("some_invalid_key")

    for port in original_outputs.values():
        assert await node_ports.get(port.key) == port.value
        await node_ports.set(port.key, port.value)


@pytest.fixture(scope="session")
def e_tag() -> str:
    return "123154654684321-1"


@pytest.fixture
async def mock_upload_file(mocker, e_tag):
    mock = mocker.patch(
        "simcore_sdk.node_ports.filemanager.upload_file",
        return_value=Future(),
    )
    mock.return_value.set_result(("0", e_tag))
    yield mock


async def test_node_ports_set_file_by_keymap(
    mock_db_manager: Callable,
    default_configuration: Dict[str, Any],
    node_uuid: str,
    mock_upload_file,
):
    db_manager = mock_db_manager(default_configuration)

    original_inputs = create_valid_port_mapping(InputsList, suffix="original")
    original_outputs = create_valid_port_mapping(
        OutputsList, suffix="original", file_to_key=Path(__file__).name
    )

    async def mock_save_db_cb(*args, **kwargs):
        pass

    async def mock_node_port_creator_cb(*args, **kwargs):
        updated_node_ports = Nodeports(
            inputs=original_inputs,
            outputs=original_outputs,
            db_manager=db_manager,
            node_uuid=node_uuid,
            save_to_db_cb=mock_save_db_cb,
            node_port_creator_cb=mock_node_port_creator_cb,
            auto_update=False,
        )
        return updated_node_ports

    node_ports = Nodeports(
        inputs=original_inputs,
        outputs=original_outputs,
        db_manager=db_manager,
        node_uuid=node_uuid,
        save_to_db_cb=mock_save_db_cb,
        node_port_creator_cb=mock_node_port_creator_cb,
        auto_update=False,
    )

    await node_ports.set_file_by_keymap(Path(__file__))

    with pytest.raises(exceptions.PortNotFound):
        await node_ports.set_file_by_keymap(Path("/whatever/file/that/is/invalid"))


async def test_node_ports_v2_packages(
    mock_db_manager: Callable, default_configuration: Dict[str, Any]
):
    db_manager = mock_db_manager(default_configuration)
    node_ports = await ports()
    node_ports = await ports(db_manager)
