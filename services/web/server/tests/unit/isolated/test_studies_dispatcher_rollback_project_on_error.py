# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

"""
Tests for rollback_project_on_error context manager behavior.
"""

import asyncio
from collections.abc import Iterator
from unittest.mock import AsyncMock, patch

import pytest
from faker import Faker
from models_library.projects import ProjectID
from simcore_service_webserver.studies_dispatcher._errors import (
    ProjectCreationAbortedError,
)
from simcore_service_webserver.studies_dispatcher._projects import (
    rollback_project_on_error,
)


@pytest.fixture
def mock_app() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def mock_delete_project_by_user() -> Iterator[AsyncMock]:
    with patch(
        "simcore_service_webserver.studies_dispatcher._projects.delete_project_by_user",
        new_callable=AsyncMock,
    ) as mock:
        yield mock


@pytest.fixture
def project_uuid(faker: Faker) -> ProjectID:
    return faker.uuid4()


async def test_cancelled_error_propagates_without_wrapping(
    mock_app,
    mock_delete_project_by_user: AsyncMock,
    project_uuid: ProjectID,
):
    """CancelledError (BaseException since Python 3.8) must NOT be caught by
    rollback_project_on_error. It should propagate directly without being
    wrapped in ProjectCreationAbortedError."""

    with pytest.raises(asyncio.CancelledError):
        async with rollback_project_on_error(mock_app, user_id=1, project_uuid=project_uuid, product_name="osparc"):
            raise asyncio.CancelledError

    # Cleanup should NOT have been triggered
    mock_delete_project_by_user.assert_not_called()


async def test_regular_exception_triggers_cleanup_and_raises_aborted_error(
    mock_app,
    mock_delete_project_by_user: AsyncMock,
    project_uuid: ProjectID,
):
    """Regular exceptions should trigger cleanup and be wrapped in
    ProjectCreationAbortedError."""

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
    project_uuid: ProjectID,
):
    """If cleanup itself fails, ProjectCreationAbortedError is still raised
    (cleanup failure is logged but swallowed)."""
    mock_delete_project_by_user.side_effect = RuntimeError("cleanup failed")

    with pytest.raises(ProjectCreationAbortedError):  # noqa: PT012
        async with rollback_project_on_error(mock_app, user_id=1, project_uuid=project_uuid, product_name="osparc"):
            msg = "original error"
            raise ValueError(msg)
