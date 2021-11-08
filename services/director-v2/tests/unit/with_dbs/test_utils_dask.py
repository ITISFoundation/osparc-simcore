# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=no-value-for-parameter
# pylint:disable=protected-access
# pylint:disable=too-many-arguments


import aiopg
import pytest
from conftest import PublishedProject
from pytest_mock.plugin import MockerFixture
from simcore_service_director_v2.models.schemas.constants import UserID
from simcore_service_director_v2.utils.dask import (
    clean_task_output_and_log_files_if_invalid,
)

pytest_simcore_core_services_selection = ["postgres"]
pytest_simcore_ops_services_selection = ["adminer"]


@pytest.fixture
async def mocked_node_ports_storage_client(mocker: MockerFixture):
    mocker.patch(
        "simcore_service_director_v2.utils.dask.port_utils.filemanager.storage_client",
        autospec=True,
    )


async def test_clean_task_output_and_log_files_if_invalid(
    aiopg_engine: aiopg.sa.engine.Engine,
    user_id: UserID,
    published_project: PublishedProject,
    mocked_node_ports_storage_client: None,
):
    await clean_task_output_and_log_files_if_invalid(
        aiopg_engine,
        user_id,
        published_project.project.uuid,
        published_project.tasks[0].node_id,
    )
