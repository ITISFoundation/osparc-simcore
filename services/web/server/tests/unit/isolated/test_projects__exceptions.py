# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from uuid import uuid4

from simcore_service_webserver.projects.exceptions import (
    ProjectDeleteError,
    ProjectsBatchDeleteError,
)


def test_projects_batch_delete_error_shows_real_error_details():
    project_uuid = uuid4()
    details = "storage service timed out"

    inner_error = ProjectDeleteError(project_uuid=project_uuid, details=details)
    batch_error = ProjectsBatchDeleteError(errors=[(project_uuid, inner_error)], deleted_project_ids=[])

    message = str(batch_error)
    assert details in message
    assert "ProjectDeleteError()" not in message


def test_projects_batch_delete_error_caps_displayed_errors_and_shows_count():
    num_failed = ProjectsBatchDeleteError._MAX_DISPLAYED_ERRORS + 5  # noqa: SLF001
    errors = [(uuid4(), ProjectDeleteError(project_uuid=uuid4(), details=f"reason {i}")) for i in range(num_failed)]

    batch_error = ProjectsBatchDeleteError(errors=errors, deleted_project_ids=[])

    message = str(batch_error)
    assert f"{num_failed} failed" in message
    assert "reason 0" in message
    # only the first _MAX_DISPLAYED_ERRORS are shown individually
    assert f"reason {ProjectsBatchDeleteError._MAX_DISPLAYED_ERRORS}" not in message  # noqa: SLF001
    assert "... and 5 more" in message


def test_projects_batch_delete_error_excludes_successfully_deleted_projects():
    project_uuid = uuid4()
    inner_error = ProjectDeleteError(project_uuid=project_uuid, details="boom")

    batch_error = ProjectsBatchDeleteError(
        errors=[(project_uuid, inner_error)],
        deleted_project_ids=["some-other-deleted-id"],
    )

    assert "some-other-deleted-id" not in str(batch_error)
