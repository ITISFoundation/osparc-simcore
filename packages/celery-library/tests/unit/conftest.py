# pylint: disable=redefined-outer-name

from unittest.mock import AsyncMock, MagicMock

import pytest
from celery_library import CeleryTaskManager
from models_library.celery import OwnerMetadata
from models_library.users import UserID


class MyOwnerMetadata(OwnerMetadata):
    user_id: UserID


@pytest.fixture
def fake_owner_metadata() -> OwnerMetadata:
    return MyOwnerMetadata(user_id=42, owner="test-owner")


@pytest.fixture
def mocked_celery_app() -> MagicMock:
    return MagicMock()


@pytest.fixture
def mocked_task_store() -> AsyncMock:
    mock = AsyncMock()
    # keep progress lookups pydantic-valid when STARTED/RETRY tasks are polled
    mock.get_task_progress.return_value = None
    return mock


@pytest.fixture
def mocked_task_manager(mocked_celery_app: MagicMock, mocked_task_store: AsyncMock) -> CeleryTaskManager:
    return CeleryTaskManager(_app=mocked_celery_app, _settings=MagicMock(), _task_store=mocked_task_store)
