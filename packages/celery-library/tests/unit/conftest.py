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
def celery_app_mock() -> MagicMock:
    return MagicMock()


@pytest.fixture
def task_store_mock() -> AsyncMock:
    mock = AsyncMock()
    # keep progress lookups pydantic-valid when STARTED/RETRY tasks are polled
    mock.get_task_progress.return_value = None
    return mock


@pytest.fixture
def task_manager_mock(celery_app_mock: MagicMock, task_store_mock: AsyncMock) -> CeleryTaskManager:
    return CeleryTaskManager(_app=celery_app_mock, _settings=MagicMock(), _task_store=task_store_mock)
