# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=no-value-for-parameter
# pylint:disable=protected-access
# pylint:disable=too-many-arguments


from typing import Dict
from unittest import mock

import aiopg
import pytest
from _helpers import PublishedProject, set_comp_task_outputs
from models_library.projects_nodes_io import SimCoreFileLink
from pytest_mock.plugin import MockerFixture
from simcore_service_director_v2.models.schemas.constants import UserID
from simcore_service_director_v2.utils.dask import (
    _LOGS_FILE_NAME,
    clean_task_output_and_log_files_if_invalid,
)

pytest_simcore_core_services_selection = ["postgres"]
pytest_simcore_ops_services_selection = ["adminer"]


@pytest.fixture
async def mocked_node_ports_filemanager_fcts(
    mocker: MockerFixture,
) -> Dict[str, mock.MagicMock]:
    return {
        "entry_exists": mocker.patch(
            "simcore_service_director_v2.utils.dask.port_utils.filemanager.entry_exists",
            autospec=True,
            return_value=False,
        ),
        "delete_file": mocker.patch(
            "simcore_service_director_v2.utils.dask.port_utils.filemanager.delete_file",
            autospec=True,
            return_value=None,
        ),
    }


@pytest.mark.parametrize("entry_exists_returns", [True, False])
async def test_clean_task_output_and_log_files_if_invalid(
    aiopg_engine: aiopg.sa.engine.Engine,  # type: ignore
    user_id: UserID,
    published_project: PublishedProject,
    mocked_node_ports_filemanager_fcts: Dict[str, mock.MagicMock],
    entry_exists_returns: bool,
):
    # since the presigned links for outputs and logs file are created
    # BEFORE the task is actually run. In case there is a failure at running
    # the task, these entries shall be cleaned up. The way to check this is
    # by asking storage if these file really exist. If not they get deleted.
    mocked_node_ports_filemanager_fcts[
        "entry_exists"
    ].return_value = entry_exists_returns

    sleeper_task = published_project.tasks[1]
    # add 2 outputs there
    outputs_schema = {
        "out_1": {
            "type": "data:text/plain",
            "label": "first output",
            "description": "whatever",
        },
        "out_2": {
            "type": "data:text/plain",
            "label": "second output",
            "description": "whatever",
        },
    }
    outputs = {
        "out_1": SimCoreFileLink(store=0, path="some/fake/test/path").dict(
            by_alias=True, exclude_unset=True
        ),
        "out_2": SimCoreFileLink(store=0, path="some/fake/test/path").dict(
            by_alias=True, exclude_unset=True
        ),
    }
    await set_comp_task_outputs(
        aiopg_engine, sleeper_task.node_id, outputs_schema, outputs
    )
    # this should ask for the 2 files + the log file
    await clean_task_output_and_log_files_if_invalid(
        aiopg_engine,
        user_id,
        published_project.project.uuid,
        published_project.tasks[1].node_id,
    )
    mocked_node_ports_filemanager_fcts["entry_exists"].assert_has_calls(
        [
            mock.call(
                user_id=user_id,
                store_id="0",
                s3_object=f"{published_project.project.uuid}/{sleeper_task.node_id}/out_1",
            ),
            mock.call(
                user_id=user_id,
                store_id="0",
                s3_object=f"{published_project.project.uuid}/{sleeper_task.node_id}/out_2",
            ),
            mock.call(
                user_id=user_id,
                store_id="0",
                s3_object=f"{published_project.project.uuid}/{sleeper_task.node_id}/{_LOGS_FILE_NAME}",
            ),
        ]
    )
    if entry_exists_returns:
        mocked_node_ports_filemanager_fcts["delete_file"].assert_not_called()
    else:
        mocked_node_ports_filemanager_fcts["delete_file"].assert_has_calls(
            [
                mock.call(
                    user_id=user_id,
                    store_id="0",
                    s3_object=f"{published_project.project.uuid}/{sleeper_task.node_id}/out_1",
                ),
                mock.call(
                    user_id=user_id,
                    store_id="0",
                    s3_object=f"{published_project.project.uuid}/{sleeper_task.node_id}/out_2",
                ),
                mock.call(
                    user_id=user_id,
                    store_id="0",
                    s3_object=f"{published_project.project.uuid}/{sleeper_task.node_id}/{_LOGS_FILE_NAME}",
                ),
            ]
        )
