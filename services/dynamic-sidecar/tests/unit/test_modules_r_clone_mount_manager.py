import pytest
from models_library.api_schemas_dynamic_sidecar.state_paths import MountActivityStatus
from simcore_service_dynamic_sidecar.modules.r_clone_mount_manager import (
    _MountActivitySummary,
    resolve_mount_activity_status,
)


@pytest.mark.parametrize(
    "files_queued, files_in_transfer, expected_status",
    [
        pytest.param(
            0,
            {},
            MountActivityStatus.FILES_UPLOAD_ENDED,
            id=MountActivityStatus.FILES_UPLOAD_ENDED,
        ),
        pytest.param(
            3,
            {},
            MountActivityStatus.FILES_UPLOAD_QUEUED,
            id=MountActivityStatus.FILES_UPLOAD_QUEUED,
        ),
        pytest.param(
            0,
            {"file1.dat": {"bytes_transferred": 100, "total_bytes": 200}},
            MountActivityStatus.FILES_UPLOAD_UPLOADING,
            id=MountActivityStatus.FILES_UPLOAD_UPLOADING,
        ),
        pytest.param(
            2,
            {"file1.dat": {"bytes_transferred": 50, "total_bytes": 100}},
            MountActivityStatus.FILES_UPLOAD_QUEUED_AND_UPLOADING,
            id=MountActivityStatus.FILES_UPLOAD_QUEUED_AND_UPLOADING,
        ),
    ],
)
def test_resolve_mount_activity_status(
    files_queued: int,
    files_in_transfer: dict,
    expected_status: MountActivityStatus,
):
    summary = _MountActivitySummary(
        files_queued=files_queued,
        files_in_transfer=files_in_transfer,
    )
    assert resolve_mount_activity_status(summary) == expected_status
