# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import asyncio
from unittest import mock

import pytest
from aiohttp.test_utils import TestClient
from pytest_mock import MockerFixture
from simcore_service_storage.dsm_cleaner import _TASK_NAME_PERIODICALY_CLEAN_DSM

pytest_simcore_core_services_selection = ["postgres"]
pytest_simcore_ops_services_selection = ["adminer"]


@pytest.fixture
def disable_dsm_cleaner(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("STORAGE_CLEANER_INTERVAL_S", "null")


@pytest.fixture
def mocked_dsm_clean(mocker: MockerFixture) -> mock.Mock:
    return mocker.patch(
        "simcore_service_storage.dsm_cleaner.SimcoreS3DataManager.clean_expired_uploads",
        autospec=True,
        side_effect=RuntimeError,
    )


@pytest.fixture
def short_dsm_cleaner_interval(monkeypatch: pytest.MonkeyPatch) -> int:
    monkeypatch.setenv("STORAGE_CLEANER_INTERVAL_S", "1")
    return 1


async def test_setup_dsm_cleaner(client: TestClient):
    all_tasks = asyncio.all_tasks()
    assert any(
        t.get_name().startswith(
            f"exclusive_periodic_task_{_TASK_NAME_PERIODICALY_CLEAN_DSM}"
        )
        for t in all_tasks
    )


async def test_disable_dsm_cleaner(disable_dsm_cleaner, client: TestClient):
    all_tasks = asyncio.all_tasks()
    assert not any(
        t.get_name().startswith(
            f"exclusive_periodic_task_{_TASK_NAME_PERIODICALY_CLEAN_DSM}"
        )
        for t in all_tasks
    )


async def test_dsm_cleaner_task_restarts_if_error(
    mocked_dsm_clean: mock.Mock, short_dsm_cleaner_interval: int, client: TestClient
):
    num_calls = mocked_dsm_clean.call_count
    await asyncio.sleep(short_dsm_cleaner_interval + 1)
    mocked_dsm_clean.assert_called()
    assert mocked_dsm_clean.call_count > num_calls
