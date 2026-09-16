# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument

import pytest
import sqlalchemy as sa
from pytest_mock import MockerFixture


@pytest.fixture(scope="module")
def postgres_db(postgres_db_from_template: sa.engine.Engine) -> sa.engine.Engine:
    # NOTE: opt-in to the session-scoped migrated template + per-module clone instead of
    # running alembic 'upgrade head'/'downgrade base' for every test module
    return postgres_db_from_template


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
