from unittest.mock import MagicMock

from aiohttp import web
from faker import Faker
from models_library.projects import ProjectID
from models_library.users import UserID
from pytest_mock import MockerFixture
from servicelib.long_running_tasks.models import TaskProgress
from simcore_service_webserver.projects import _crud_api_create
from yarl import URL


async def test_create_project_locks_source_before_reading_it(
    faker: Faker,
    mocker: MockerFixture,
):
    source_project_id = ProjectID(faker.uuid4())
    lock_is_held = False

    async def _create_project_unlocked(*_args, **_kwargs) -> web.HTTPCreated:
        assert lock_is_held
        return web.HTTPCreated()

    mocker.patch.object(
        _crud_api_create,
        "_create_project_unlocked",
        side_effect=_create_project_unlocked,
    )
    mocker.patch.object(
        _crud_api_create,
        "get_redis_lock_manager_client_sdk",
        return_value=MagicMock(),
    )

    def _with_project_locked(*_args, **kwargs):
        assert kwargs["project_uuid"] == source_project_id

        def _decorator(operation):
            async def _run_locked():
                nonlocal lock_is_held
                lock_is_held = True
                try:
                    return await operation()
                finally:
                    lock_is_held = False

            return _run_locked

        return _decorator

    mocker.patch.object(_crud_api_create, "with_project_locked", side_effect=_with_project_locked)

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
