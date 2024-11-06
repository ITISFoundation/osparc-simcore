# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=protected-access

from pathlib import Path
from typing import Any, Callable
from unittest.mock import AsyncMock

import pytest
from faker import Faker
from pydantic import ValidationError
from pytest_mock import MockFixture
from servicelib.progress_bar import ProgressBarData
from simcore_sdk.node_ports_common.filemanager import UploadedFile
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
    default_configuration: dict[str, Any],
    user_id: int,
    project_id: str,
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
        return Nodeports(
            inputs=updated_inputs,
            outputs=updated_outputs,
            db_manager=db_manager,
            user_id=user_id,
            project_id=project_id,
            node_uuid=node_uuid,
            io_log_redirect_cb=None,
            save_to_db_cb=mock_save_db_cb,
            node_port_creator_cb=mock_node_port_creator_cb,
            auto_update=False,
        )

    node_ports = Nodeports(
        inputs=original_inputs,
        outputs=original_outputs,
        db_manager=db_manager,
        user_id=user_id,
        project_id=project_id,
        node_uuid=node_uuid,
        io_log_redirect_cb=None,
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
    default_configuration: dict[str, Any],
    user_id: int,
    project_id: str,
    node_uuid: str,
    faker: Faker,
):
    db_manager = mock_db_manager(default_configuration)

    original_inputs = create_valid_port_mapping(InputsList, suffix="original")
    original_outputs = create_valid_port_mapping(OutputsList, suffix="original")

    async def mock_save_db_cb(*args, **kwargs):
        pass

    async def mock_node_port_creator_cb(*args, **kwargs):
        return Nodeports(
            inputs=original_inputs,
            outputs=original_outputs,
            db_manager=db_manager,
            user_id=user_id,
            project_id=project_id,
            node_uuid=node_uuid,
            io_log_redirect_cb=None,
            save_to_db_cb=mock_save_db_cb,
            node_port_creator_cb=mock_node_port_creator_cb,
            auto_update=False,
        )

    node_ports = Nodeports(
        inputs=original_inputs,
        outputs=original_outputs,
        db_manager=db_manager,
        user_id=user_id,
        project_id=project_id,
        node_uuid=node_uuid,
        io_log_redirect_cb=None,
        save_to_db_cb=mock_save_db_cb,
        node_port_creator_cb=mock_node_port_creator_cb,
        auto_update=False,
    )

    for port in original_inputs.values():
        assert await node_ports.get(port.key) == port.value
        await node_ports.set(port.key, port.value)

    with pytest.raises(exceptions.UnboundPortError):
        await node_ports.get("some_invalid_key")  # type: ignore

    for port in original_outputs.values():
        assert await node_ports.get(port.key) == port.value
        await node_ports.set(port.key, port.value)

    # test batch add
    async with ProgressBarData(num_steps=1, description=faker.pystr()) as progress_bar:
        await node_ports.set_multiple(
            {
                port.key: (port.value, None)
                for port in list(original_inputs.values())
                + list(original_outputs.values())
            },
            progress_bar=progress_bar,
            outputs_callbacks=AsyncMock(),
        )
    assert progress_bar._current_steps == pytest.approx(1)  # noqa: SLF001


@pytest.fixture(scope="session")
def e_tag() -> str:
    return "123154654684321-1"


@pytest.fixture
async def mock_upload_path(mocker: MockFixture, e_tag: str) -> MockFixture:
    return mocker.patch(
        "simcore_sdk.node_ports_common.filemanager.upload_path",
        return_value=UploadedFile(0, e_tag),
        autospec=True,
    )


async def test_node_ports_set_file_by_keymap(
    mock_db_manager: Callable,
    default_configuration: dict[str, Any],
    user_id: int,
    project_id: str,
    node_uuid: str,
    mock_upload_path: MockFixture,
):
    db_manager = mock_db_manager(default_configuration)

    original_inputs = create_valid_port_mapping(InputsList, suffix="original")
    original_outputs = create_valid_port_mapping(
        OutputsList, suffix="original", file_to_key=Path(__file__).name
    )

    async def mock_save_db_cb(*args, **kwargs):
        pass

    async def mock_node_port_creator_cb(*args, **kwargs):
        return Nodeports(
            inputs=original_inputs,
            outputs=original_outputs,
            db_manager=db_manager,
            user_id=user_id,
            project_id=project_id,
            node_uuid=node_uuid,
            io_log_redirect_cb=None,
            save_to_db_cb=mock_save_db_cb,
            node_port_creator_cb=mock_node_port_creator_cb,
            auto_update=False,
        )

    node_ports = Nodeports(
        inputs=original_inputs,
        outputs=original_outputs,
        db_manager=db_manager,
        user_id=user_id,
        project_id=project_id,
        node_uuid=node_uuid,
        io_log_redirect_cb=None,
        save_to_db_cb=mock_save_db_cb,
        node_port_creator_cb=mock_node_port_creator_cb,
        auto_update=False,
    )

    await node_ports.set_file_by_keymap(Path(__file__))

    with pytest.raises(exceptions.PortNotFound):
        await node_ports.set_file_by_keymap(Path("/whatever/file/that/is/invalid"))


async def test_node_ports_v2_packages(
    mock_db_manager: Callable,
    default_configuration: dict[str, Any],
    user_id: int,
    project_id: str,
    node_uuid: str,
):
    db_manager = mock_db_manager(default_configuration)
    node_ports = await ports(user_id, project_id, node_uuid)
    node_ports = await ports(user_id, project_id, node_uuid, db_manager=db_manager)


@pytest.fixture
def mock_port_set(mocker: MockFixture) -> None:
    async def _always_raise_error(*args, **kwargs):
        raise ValidationError.from_exception_data(title="Just a test", line_errors=[])

    mocker.patch(
        "simcore_sdk.node_ports_v2.port.Port._set", side_effect=_always_raise_error
    )


async def test_node_ports_v2_set_multiple_catch_multiple_failing_set_ports(
    mock_port_set: None,
    mock_db_manager: Callable,
    default_configuration: dict[str, Any],
    user_id: int,
    project_id: str,
    node_uuid: str,
    faker: Faker,
):
    db_manager = mock_db_manager(default_configuration)

    original_inputs = create_valid_port_mapping(InputsList, suffix="original")
    original_outputs = create_valid_port_mapping(OutputsList, suffix="original")

    async def _mock_callback(*args, **kwargs):
        pass

    node_ports = Nodeports(
        inputs=original_inputs,
        outputs=original_outputs,
        db_manager=db_manager,
        user_id=user_id,
        project_id=project_id,
        node_uuid=node_uuid,
        io_log_redirect_cb=None,
        save_to_db_cb=_mock_callback,
        node_port_creator_cb=_mock_callback,
        auto_update=False,
    )
    async with ProgressBarData(num_steps=1, description=faker.pystr()) as progress_bar:
        with pytest.raises(ValidationError):
            await node_ports.set_multiple(
                {
                    port.key: (port.value, None)
                    for port in list(original_inputs.values())
                    + list(original_outputs.values())
                },
                progress_bar=progress_bar,
                outputs_callbacks=None,
            )
