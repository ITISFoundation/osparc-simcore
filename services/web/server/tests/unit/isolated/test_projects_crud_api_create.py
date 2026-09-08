from collections.abc import Callable, Coroutine
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiohttp import web
from faker import Faker
from models_library.projects import ProjectID
from models_library.users import UserID
from pytest_mock import MockerFixture
from servicelib.long_running_tasks.models import TaskProgress
from servicelib.long_running_tasks.task import TaskRegistry
from simcore_service_webserver.projects import _crud_api_create, _projects_service
from simcore_service_webserver.projects.exceptions import (
    ProjectCloningConflictError,
    ProjectCopyingTrashedProjectError,
    ProjectInvalidRightsError,
)
from simcore_service_webserver.projects.models import ProjectDict
from yarl import URL

type _CreateProjectOperation = Callable[[ProjectDict], Coroutine[Any, Any, web.HTTPCreated]]


async def test_create_project_locks_source_before_reading_it(
    faker: Faker,
    mocker: MockerFixture,
):
    source_project_id = ProjectID(faker.uuid4())
    lock_is_held = False

    async def _create_project_unlocked(*_args: Any, **_kwargs: Any) -> web.HTTPCreated:
        assert lock_is_held
        return web.HTTPCreated()

    mocker.patch.object(
        _crud_api_create,
        "_create_project_unlocked",
        side_effect=_create_project_unlocked,
    )

    async def _run_project_clone_locked(
        *_args: Any,
        operation: _CreateProjectOperation,
        **kwargs: Any,
    ) -> web.HTTPCreated:
        nonlocal lock_is_held
        assert kwargs["project_uuid"] == source_project_id
        lock_is_held = True
        try:
            return await operation(MagicMock())
        finally:
            lock_is_held = False

    mocker.patch.object(
        _projects_service,
        "run_project_clone_locked",
        side_effect=_run_project_clone_locked,
    )

    response = await _crud_api_create.create_project(
        TaskProgress.create(),
        app=MagicMock(),
        request_url=URL("http://example.test/v0/projects"),
        request_headers={},
        new_project_was_hidden_before_data_was_copied=True,
        from_study=source_project_id,
        as_template=False,
        copy_data=True,
        user_id=UserID(1),
        product_name="osparc",
        product_api_base_url="http://example.test",
        predefined_project=None,
        parent_project_uuid=None,
        parent_node_id=None,
    )

    assert response.status == 201
    assert lock_is_held is False


async def test_create_project_maps_source_lock_contention_to_domain_conflict(
    faker: Faker,
    mocker: MockerFixture,
):
    source_project_id = ProjectID(faker.uuid4())
    mocker.patch.object(
        _projects_service,
        "run_project_clone_locked",
        side_effect=ProjectCloningConflictError(project_uuid=source_project_id),
    )

    with pytest.raises(ProjectCloningConflictError):
        await _crud_api_create.create_project(
            TaskProgress.create(),
            app=MagicMock(),
            request_url=URL("http://example.test/v0/projects"),
            request_headers={},
            new_project_was_hidden_before_data_was_copied=True,
            from_study=source_project_id,
            as_template=False,
            copy_data=True,
            user_id=UserID(1),
            product_name="osparc",
            product_api_base_url="http://example.test",
            predefined_project=None,
            parent_project_uuid=None,
            parent_node_id=None,
        )


async def test_create_project_checks_source_access_before_acquiring_lock(
    faker: Faker,
    mocker: MockerFixture,
):
    source_project_id = ProjectID(faker.uuid4())
    mocker.patch.object(
        _projects_service,
        "get_project_for_user",
        side_effect=ProjectInvalidRightsError(
            project_uuid=source_project_id,
            user_id=UserID(1),
        ),
    )
    mocked_with_project_locked = mocker.patch.object(_projects_service, "with_project_locked")
    mocked_with_project_read_locked = mocker.patch.object(_projects_service, "with_project_read_locked")
    operation = AsyncMock()

    with pytest.raises(ProjectInvalidRightsError):
        await _projects_service.run_project_clone_locked(
            app=MagicMock(),
            project_uuid=source_project_id,
            user_id=UserID(1),
            operation=operation,
        )

    mocked_with_project_locked.assert_not_called()
    mocked_with_project_read_locked.assert_not_called()
    operation.assert_not_awaited()


def test_register_create_project_task_allows_expected_domain_conflicts(
    mocker: MockerFixture,
):
    mocker.patch.object(TaskRegistry, "_REGISTERED_TASKS", {})

    _crud_api_create.register_create_project_task(MagicMock())

    allowed_errors = TaskRegistry.get_allowed_errors(_crud_api_create.create_project.__name__)
    assert ProjectCloningConflictError in allowed_errors
    assert ProjectCopyingTrashedProjectError in allowed_errors
