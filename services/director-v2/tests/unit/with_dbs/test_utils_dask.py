# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=no-value-for-parameter
# pylint:disable=protected-access
# pylint:disable=too-many-arguments
# pylint:disable=no-name-in-module


import uuid
from random import choice
from typing import Any, Dict
from unittest import mock

import aiopg
import pytest
from _helpers import PublishedProject, set_comp_task_outputs  # type: ignore
from dask_task_models_library.container_tasks.io import FileUrl, TaskOutputData
from faker import Faker
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID, SimCoreFileLink
from pydantic.tools import parse_obj_as
from pytest_mock.plugin import MockerFixture
from simcore_service_director_v2.models.domains.comp_tasks import CompTaskAtDB
from simcore_service_director_v2.models.schemas.constants import UserID
from simcore_service_director_v2.utils.dask import (
    _LOGS_FILE_NAME,
    clean_task_output_and_log_files_if_invalid,
    generate_dask_job_id,
    parse_dask_job_id,
    parse_output_data,
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


@pytest.fixture(
    params=["simcore/service/comp/some/fake/service/key", "dockerhub-style/service_key"]
)
def service_key(request) -> str:
    return request.param


@pytest.fixture()
def service_version() -> str:
    return "1234.32432.2344"


@pytest.fixture()
def project_id() -> ProjectID:
    return uuid.uuid4()


@pytest.fixture()
def node_id() -> NodeID:
    return uuid.uuid4()


def test_dask_job_id_serialization(
    service_key: str,
    service_version: str,
    user_id: UserID,
    project_id: ProjectID,
    node_id: NodeID,
):
    dask_job_id = generate_dask_job_id(
        service_key, service_version, user_id, project_id, node_id
    )
    (
        parsed_service_key,
        parsed_service_version,
        parsed_user_id,
        parsed_project_id,
        parsed_node_id,
    ) = parse_dask_job_id(dask_job_id)
    assert service_key == parsed_service_key
    assert service_version == parsed_service_version
    assert user_id == parsed_user_id
    assert project_id == parsed_project_id
    assert node_id == parsed_node_id


@pytest.fixture()
def fake_output_config() -> Dict[str, str]:
    return {
        "out_1": "integer",
        "out_2": "data:*/*",
        "out_3": "boolean",
        "out_4": "number",
        "out_5": "string",
        "out_23": "data:*/*",
    }


@pytest.fixture()
def fake_outputs_schema(fake_output_config: Dict[str, str], faker: Faker):
    fake_outputs_schema = {
        key: {
            "type": value_type,
            "label": faker.pystr(),
            "description": faker.pystr(),
        }
        for key, value_type in fake_output_config.items()
    }
    return fake_outputs_schema


@pytest.fixture()
def fake_task_output_data(
    fake_output_config: Dict[str, str], faker: Faker
) -> TaskOutputData:
    def generate_random_file_url() -> Dict[str, Any]:
        return {"url": faker.url(), "file_mapping": choice([faker.file_name(), None])}

    TYPE_TO_FAKE_CALLABLE_MAP = {
        "number": faker.pyfloat,
        "integer": faker.pyint,
        "string": faker.pystr,
        "boolean": faker.pybool,
        "data:*/*": generate_random_file_url,
    }
    data = parse_obj_as(
        TaskOutputData,
        {
            key: TYPE_TO_FAKE_CALLABLE_MAP[value_type]()
            for key, value_type in fake_output_config.items()
        },
    )
    return data


async def test_parse_output_data(
    aiopg_engine: aiopg.sa.engine.Engine,  # type: ignore
    published_project: PublishedProject,
    user_id: UserID,
    fake_outputs_schema: Dict[str, Any],
    fake_task_output_data: TaskOutputData,
    mocker: MockerFixture,
    faker: Faker,
):
    # need some fakes set in the DB
    sleeper_task: CompTaskAtDB = published_project.tasks[1]
    no_outputs = {}
    await set_comp_task_outputs(
        aiopg_engine, sleeper_task.node_id, fake_outputs_schema, no_outputs
    )
    # mock the set_value function so we can test it is called correctly
    mocked_node_ports_set_value_fct = mocker.patch(
        "simcore_sdk.node_ports_v2.port.Port.set_value"
    )

    # test
    dask_job_id = generate_dask_job_id(
        sleeper_task.image.name,
        sleeper_task.image.tag,
        user_id,
        published_project.project.uuid,
        sleeper_task.node_id,
    )
    await parse_output_data(aiopg_engine, dask_job_id, fake_task_output_data)

    # the FileUrl types are converted to a pure url
    expected_values = {
        k: v.url if isinstance(v, FileUrl) else v
        for k, v in fake_task_output_data.items()
    }
    mocked_node_ports_set_value_fct.assert_has_calls(
        [mock.call(value) for value in expected_values.values()]
    )


@pytest.mark.parametrize("entry_exists_returns", [True, False])
async def test_clean_task_output_and_log_files_if_invalid(
    aiopg_engine: aiopg.sa.engine.Engine,  # type: ignore
    user_id: UserID,
    published_project: PublishedProject,
    mocked_node_ports_filemanager_fcts: Dict[str, mock.MagicMock],
    entry_exists_returns: bool,
    fake_outputs_schema: Dict[str, Any],
    faker: Faker,
):
    # since the presigned links for outputs and logs file are created
    # BEFORE the task is actually run. In case there is a failure at running
    # the task, these entries shall be cleaned up. The way to check this is
    # by asking storage if these file really exist. If not they get deleted.
    mocked_node_ports_filemanager_fcts[
        "entry_exists"
    ].return_value = entry_exists_returns

    sleeper_task = published_project.tasks[1]

    # simulate pre-created file links
    fake_outputs = {
        key: SimCoreFileLink(store=0, path=faker.file_path()).dict(
            by_alias=True, exclude_unset=True
        )
        for key, value_type in fake_outputs_schema.items()
        if value_type["type"] == "data:*/*"
    }
    await set_comp_task_outputs(
        aiopg_engine, sleeper_task.node_id, fake_outputs_schema, fake_outputs
    )
    # this should ask for the 2 files + the log file
    await clean_task_output_and_log_files_if_invalid(
        aiopg_engine,
        user_id,
        published_project.project.uuid,
        published_project.tasks[1].node_id,
    )
    expected_calls = [
        mock.call(
            user_id=user_id,
            store_id="0",
            s3_object=f"{published_project.project.uuid}/{sleeper_task.node_id}/{key}",
        )
        for key in fake_outputs.keys()
    ] + [
        mock.call(
            user_id=user_id,
            store_id="0",
            s3_object=f"{published_project.project.uuid}/{sleeper_task.node_id}/{_LOGS_FILE_NAME}",
        )
    ]
    mocked_node_ports_filemanager_fcts["entry_exists"].assert_has_calls(expected_calls)
    if entry_exists_returns:
        mocked_node_ports_filemanager_fcts["delete_file"].assert_not_called()
    else:
        mocked_node_ports_filemanager_fcts["delete_file"].assert_has_calls(
            expected_calls
        )
