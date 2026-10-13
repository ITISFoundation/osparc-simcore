# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument

import pytest
from pytest_mock import MockerFixture

pytest_plugins = [
    "pytest_simcore.xdist_docker_daemon",
]


@pytest.fixture
def disable_dsm_cleaner(mocker: MockerFixture) -> None:
    mocker.patch(
        "simcore_service_storage.dsm_cleaner.clean_expired_uploads",
        autospec=True,
    )


@pytest.fixture
def disable_dsm_export_cleaner(mocker: MockerFixture) -> None:
    mocker.patch(
        "simcore_service_storage.dsm_cleaner.clean_expired_exports",
        autospec=True,
    )


@pytest.fixture
def disable_all_dsm_cleaner_tasks(disable_dsm_cleaner: None, disable_dsm_export_cleaner: None) -> None:
    pass
