# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import asyncio
from datetime import timedelta
from unittest import mock

import pytest
from fastapi import FastAPI
from pytest_mock import MockerFixture
from simcore_service_storage.core.settings import get_application_settings
from simcore_service_storage.dsm_cleaner import (
    _TASK_NAME_CLEAN_EXPIRED_EXPORTS,
    _TASK_NAME_CLEAN_EXPIRED_UPLOADS,
)

pytest_simcore_core_services_selection = ["postgres", "rabbit"]
pytest_simcore_ops_services_selection = ["adminer"]


@pytest.fixture
def mocked_dsm_clean(mocker: MockerFixture) -> mock.Mock:
    return mocker.patch(
        "simcore_service_storage.dsm_cleaner.SimcoreS3DataManager.clean_expired_uploads",
        autospec=True,
        side_effect=RuntimeError,
    )


@pytest.fixture
def mocked_dsm_export_clean(mocker: MockerFixture) -> mock.Mock:
    return mocker.patch(
        "simcore_service_storage.dsm_cleaner.SimcoreS3DataManager.clean_expired_exports",
        autospec=True,
        side_effect=RuntimeError,
    )


@pytest.fixture
def short_dsm_cleaner_interval(monkeypatch: pytest.MonkeyPatch) -> int:
    monkeypatch.setenv("STORAGE_CLEANER", '{"STORAGE_CLEANER_EXPIRE_UPLOADS_INTERVAL": "PT1S"}')
    return 1


@pytest.fixture
def short_dsm_export_cleaner_interval(monkeypatch: pytest.MonkeyPatch) -> int:
    monkeypatch.setenv("STORAGE_CLEANER", '{"STORAGE_CLEANER_EXPORT_INTERVAL": "PT1S"}')
    return 1


async def test_setup_dsm_cleaner(initialized_app: FastAPI):
    all_tasks = asyncio.all_tasks()
    assert any(t.get_name().startswith(f"{_TASK_NAME_CLEAN_EXPIRED_UPLOADS}") for t in all_tasks)


async def test_clean_expired_uploads_restarts_if_error(
    mocked_dsm_clean: mock.Mock,
    short_dsm_cleaner_interval: int,
    initialized_app: FastAPI,
):
    num_calls = mocked_dsm_clean.call_count
    await asyncio.sleep(short_dsm_cleaner_interval + 1)
    mocked_dsm_clean.assert_called()
    assert mocked_dsm_clean.call_count > num_calls


async def test_setup_dsm_export_cleaner(initialized_app: FastAPI):
    all_tasks = asyncio.all_tasks()
    assert any(t.get_name().startswith(f"{_TASK_NAME_CLEAN_EXPIRED_EXPORTS}") for t in all_tasks)


async def test_dsm_export_cleaner_interval_is_a_timedelta(initialized_app: FastAPI):
    settings = get_application_settings(initialized_app)
    interval = settings.STORAGE_CLEANER.STORAGE_CLEANER_EXPORT_INTERVAL
    assert isinstance(interval, timedelta)
    assert interval == timedelta(hours=6)


async def test_clean_expired_exports_restarts_if_error(
    mocked_dsm_export_clean: mock.Mock,
    short_dsm_export_cleaner_interval: int,
    initialized_app: FastAPI,
):
    num_calls = mocked_dsm_export_clean.call_count
    await asyncio.sleep(short_dsm_export_cleaner_interval + 1)
    mocked_dsm_export_clean.assert_called()
    assert mocked_dsm_export_clean.call_count > num_calls
