# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

"""
Tests for rollback_project_on_error context manager behavior.
"""

import asyncio
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from simcore_service_webserver.studies_dispatcher._errors import (
    ProjectCreationAbortedError,
)
from simcore_service_webserver.studies_dispatcher._projects import (
    rollback_project_on_error,
)


@pytest.fixture
def mock_app():
    return AsyncMock()


@pytest.fixture
def mock_delete_project_by_user():
    with patch(
        "simcore_service_webserver.studies_dispatcher._projects.delete_project_by_user",
        new_callable=AsyncMock,
    ) as mock:
        yield mock


async def test_cancelled_error_propagates_without_wrapping(
    mock_app,
    mock_delete_project_by_user: AsyncMock,
):
    """CancelledError (BaseException in Python 3.9+) must NOT be caught by
    rollback_project_on_error. It should propagate directly without being
    wrapped in ProjectCreationAbortedError."""
    project_uuid = uuid4()

    with pytest.raises(asyncio.CancelledError):
        async with rollback_project_on_error(mock_app, user_id=1, project_uuid=project_uuid, product_name="osparc"):
            raise asyncio.CancelledError

    # Cleanup should NOT have been triggered
    mock_delete_project_by_user.assert_not_called()


async def test_regular_exception_triggers_cleanup_and_raises_aborted_error(
    mock_app,
    mock_delete_project_by_user: AsyncMock,
):
    """Regular exceptions should trigger cleanup and be wrapped in
    ProjectCreationAbortedError."""
    project_uuid = uuid4()

    with pytest.raises(ProjectCreationAbortedError):  # noqa: PT012
        async with rollback_project_on_error(mock_app, user_id=1, project_uuid=project_uuid, product_name="osparc"):
            msg = "something failed"
            raise RuntimeError(msg)

    mock_delete_project_by_user.assert_called_once_with(
        mock_app,
        project_uuid=project_uuid,
        user_id=1,
        product_name="osparc",
        wait_until_completed=False,
    )


async def test_cleanup_failure_still_raises_aborted_error(
    mock_app,
    mock_delete_project_by_user: AsyncMock,
):
    """If cleanup itself fails, ProjectCreationAbortedError is still raised
    (cleanup failure is logged but swallowed)."""
    project_uuid = uuid4()
    mock_delete_project_by_user.side_effect = RuntimeError("cleanup failed")

    with pytest.raises(ProjectCreationAbortedError):  # noqa: PT012
        async with rollback_project_on_error(mock_app, user_id=1, project_uuid=project_uuid, product_name="osparc"):
            msg = "original error"
            raise ValueError(msg)
