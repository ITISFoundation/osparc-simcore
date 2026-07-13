# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_mock import MockerFixture
from simcore_service_dynamic_sidecar.modules import long_running_tasks
from simcore_service_dynamic_sidecar.modules.outputs import UploadPortsFailedError

_MODULE = "simcore_service_dynamic_sidecar.modules.long_running_tasks"


@pytest.fixture
def progress() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def app() -> MagicMock:
    return MagicMock()


@pytest.fixture
def outputs_manager() -> MagicMock:
    manager = MagicMock()
    manager.wait_for_all_uploads_to_finish = AsyncMock()
    return manager


@pytest.fixture
def mock_post_sidecar_log_message(mocker: MockerFixture) -> AsyncMock:
    return mocker.patch(f"{_MODULE}.post_sidecar_log_message", autospec=True)


@pytest.fixture
def mock_ensure_permissions(mocker: MockerFixture) -> AsyncMock:
    return mocker.patch(f"{_MODULE}.ensure_permissions_on_user_service_data", autospec=True)


async def test_push_output_ports_success_does_not_touch_permissions(
    progress: AsyncMock,
    app: MagicMock,
    outputs_manager: MagicMock,
    mock_post_sidecar_log_message: AsyncMock,
    mock_ensure_permissions: AsyncMock,
):
    outputs_manager.wait_for_all_uploads_to_finish.side_effect = [None]

    await long_running_tasks.push_user_services_output_ports(progress, app, outputs_manager)

    assert outputs_manager.wait_for_all_uploads_to_finish.await_count == 1
    mock_ensure_permissions.assert_not_awaited()
    outputs_manager.set_all_ports_for_upload.assert_not_called()


async def test_push_output_ports_fixes_permissions_and_retries(
    progress: AsyncMock,
    app: MagicMock,
    outputs_manager: MagicMock,
    mock_post_sidecar_log_message: AsyncMock,
    mock_ensure_permissions: AsyncMock,
):
    outputs_manager.wait_for_all_uploads_to_finish.side_effect = [
        UploadPortsFailedError(failures={}),
        None,
    ]

    await long_running_tasks.push_user_services_output_ports(progress, app, outputs_manager)

    assert outputs_manager.wait_for_all_uploads_to_finish.await_count == 2
    mock_ensure_permissions.assert_awaited_once_with(app.state.mounted_volumes)
    outputs_manager.set_all_ports_for_upload.assert_called_once_with()


async def test_push_output_ports_reraises_when_retry_still_fails(
    progress: AsyncMock,
    app: MagicMock,
    outputs_manager: MagicMock,
    mock_post_sidecar_log_message: AsyncMock,
    mock_ensure_permissions: AsyncMock,
):
    outputs_manager.wait_for_all_uploads_to_finish.side_effect = [
        UploadPortsFailedError(failures={}),
        UploadPortsFailedError(failures={}),
    ]

    with pytest.raises(UploadPortsFailedError):
        await long_running_tasks.push_user_services_output_ports(progress, app, outputs_manager)

    assert outputs_manager.wait_for_all_uploads_to_finish.await_count == 2
    mock_ensure_permissions.assert_awaited_once_with(app.state.mounted_volumes)
    outputs_manager.set_all_ports_for_upload.assert_called_once_with()


async def test_push_output_ports_raises_when_permission_fix_fails(
    progress: AsyncMock,
    app: MagicMock,
    outputs_manager: MagicMock,
    mock_post_sidecar_log_message: AsyncMock,
    mock_ensure_permissions: AsyncMock,
):
    original_error = UploadPortsFailedError(failures={})
    outputs_manager.wait_for_all_uploads_to_finish.side_effect = original_error

    permissions_error = RuntimeError("could not exec chmod in container")
    mock_ensure_permissions.side_effect = permissions_error

    with pytest.raises(RuntimeError) as exc_info:
        await long_running_tasks.push_user_services_output_ports(progress, app, outputs_manager)

    # the permission-fix error is surfaced, with the original upload error kept as context
    assert exc_info.value is permissions_error
    assert exc_info.value.__context__ is original_error
    # the retry upload is never attempted if fixing permissions fails
    assert outputs_manager.wait_for_all_uploads_to_finish.await_count == 1
    outputs_manager.set_all_ports_for_upload.assert_not_called()
