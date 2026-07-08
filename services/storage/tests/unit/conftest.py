import pytest
from pytest_mock import MockerFixture


@pytest.fixture
def disable_dsm_cleaner(mocker: MockerFixture) -> None:
    return mocker.patch(
        "simcore_service_storage.dsm_cleaner.SimcoreS3DataManager.clean_expired_uploads",
        autospec=True,
    )


@pytest.fixture
def disable_dsm_export_cleaner(mocker: MockerFixture) -> None:
    return mocker.patch(
        "simcore_service_storage.dsm_cleaner.SimcoreS3DataManager.clean_expired_exports",
        autospec=True,
    )


@pytest.fixture
def disable_all_dsm_cleanup_tasks(disable_dsm_cleaner: None, disable_dsm_export_cleaner: None) -> None: ...
