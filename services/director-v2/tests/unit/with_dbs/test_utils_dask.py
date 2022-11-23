# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=no-value-for-parameter
# pylint:disable=protected-access
# pylint:disable=too-many-arguments
# pylint:disable=no-name-in-module


from random import choice
from typing import Any, Callable
from unittest import mock

import aiopg
import httpx
import pytest
from _helpers import PublishedProject, set_comp_task_inputs, set_comp_task_outputs
from dask_task_models_library.container_tasks.io import (
    FilePortSchema,
    FileUrl,
    TaskOutputData,
)
from faker import Faker
from models_library.api_schemas_storage import FileUploadLinks, FileUploadSchema
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID, SimCoreFileLink, SimcoreS3FileID
from models_library.users import UserID
from pydantic import ByteSize
from pydantic.networks import AnyUrl
from pydantic.tools import parse_obj_as
from pytest import MonkeyPatch
from pytest_mock.plugin import MockerFixture
from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_sdk.node_ports_v2 import FileLinkType
from simcore_service_director_v2.models.domains.comp_tasks import CompTaskAtDB
from simcore_service_director_v2.models.schemas.services import NodeRequirements
from simcore_service_director_v2.utils.dask import (
    _LOGS_FILE_NAME,
    clean_task_output_and_log_files_if_invalid,
    compute_input_data,
    compute_output_data_schema,
    from_node_reqs_to_dask_resources,
    generate_dask_job_id,
    parse_dask_job_id,
    parse_output_data,
)
from yarl import URL

pytest_simcore_core_services_selection = [
    "postgres",
]
pytest_simcore_ops_services_selection = [
    "adminer",
]


@pytest.fixture
async def mocked_node_ports_filemanager_fcts(
    mocker: MockerFixture,
    faker: Faker,
    tasks_file_link_scheme: tuple,
) -> dict[str, mock.MagicMock]:
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
        "get_upload_links_from_s3": mocker.patch(
            "simcore_service_director_v2.utils.dask.port_utils.filemanager.get_upload_links_from_s3",
            autospec=True,
            side_effect=lambda **kwargs: (
                0,
                FileUploadSchema(
                    urls=[
                        parse_obj_as(
                            AnyUrl,
                            f"{URL(faker.uri()).with_scheme(choice(tasks_file_link_scheme))}",
                        )
                    ],
                    chunk_size=parse_obj_as(ByteSize, "5GiB"),
                    links=FileUploadLinks(
                        abort_upload=parse_obj_as(AnyUrl, "https://www.fakeabort.com"),
                        complete_upload=parse_obj_as(
                            AnyUrl, "https://www.fakecomplete.com"
                        ),
                    ),
                ),
            ),
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


@pytest.fixture
def user_id(faker: Faker) -> UserID:
    return faker.pyint(min_value=1)


@pytest.fixture
def project_id(faker: Faker) -> ProjectID:
    return ProjectID(faker.uuid4())


@pytest.fixture
def node_id(faker: Faker) -> NodeID:
    return NodeID(faker.uuid4())


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
def fake_io_config(faker: Faker) -> dict[str, str]:
    return {
        f"pytest_io_key_{faker.pystr()}": choice(
            ["integer", "data:*/*", "boolean", "number", "string"]
        )
        for n in range(20)
    }


@pytest.fixture(params=[True, False])
def fake_io_schema(
    fake_io_config: dict[str, str], faker: Faker, request
) -> dict[str, dict[str, str]]:
    fake_io_schema = {}
    for key, value_type in fake_io_config.items():
        fake_io_schema[key] = {
            "type": value_type,
            "label": faker.pystr(),
            "description": faker.pystr(),
        }
        if value_type == "data:*/*" and request.param:
            fake_io_schema[key]["fileToKeyMap"] = {faker.file_name(): key}

    return fake_io_schema


@pytest.fixture()
def fake_io_data(
    fake_io_config: dict[str, str],
    create_simcore_file_id: Callable[[ProjectID, NodeID, str], SimcoreS3FileID],
    faker: Faker,
) -> dict[str, Any]:
    def generate_simcore_file_link() -> dict[str, Any]:
        return SimCoreFileLink(
            store=0,
            path=create_simcore_file_id(
                faker.uuid4(), faker.uuid4(), faker.file_name()
            ),
        ).dict(by_alias=True, exclude_unset=True)

    TYPE_TO_FAKE_CALLABLE_MAP = {
        "number": faker.pyfloat,
        "integer": faker.pyint,
        "string": faker.pystr,
        "boolean": faker.pybool,
        "data:*/*": generate_simcore_file_link,
    }
    return {
        key: TYPE_TO_FAKE_CALLABLE_MAP[value_type]()
        for key, value_type in fake_io_config.items()
    }


@pytest.fixture()
def fake_task_output_data(
    fake_io_schema: dict[str, dict[str, str]],
    fake_io_data: dict[str, Any],
    faker: Faker,
) -> TaskOutputData:
    converted_data = {
        key: {
            "url": faker.url(),
            "file_mapping": next(iter(fake_io_schema[key]["fileToKeyMap"]))
            if "fileToKeyMap" in fake_io_schema[key]
            else None,
        }
        if fake_io_schema[key]["type"] == "data:*/*"
        else value
        for key, value in fake_io_data.items()
    }
    data = parse_obj_as(TaskOutputData, converted_data)
    assert data
    return data


async def test_parse_output_data(
    aiopg_engine: aiopg.sa.engine.Engine,  # type: ignore
    published_project: PublishedProject,
    user_id: UserID,
    fake_io_schema: dict[str, dict[str, str]],
    fake_task_output_data: TaskOutputData,
    mocker: MockerFixture,
):
    # need some fakes set in the DB
    sleeper_task: CompTaskAtDB = published_project.tasks[1]
    no_outputs = {}
    await set_comp_task_outputs(
        aiopg_engine, sleeper_task.node_id, fake_io_schema, no_outputs
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


@pytest.fixture
def app_with_db(
    mock_env: EnvVarsDict,
    monkeypatch: MonkeyPatch,
    postgres_host_config: dict[str, str],
):
    monkeypatch.setenv("DIRECTOR_V2_POSTGRES_ENABLED", "1")
    monkeypatch.setenv("R_CLONE_PROVIDER", "MINIO")
    monkeypatch.setenv("S3_ENDPOINT", "endpoint")
    monkeypatch.setenv("S3_ACCESS_KEY", "access_key")
    monkeypatch.setenv("S3_SECRET_KEY", "secret_key")
    monkeypatch.setenv("S3_BUCKET_NAME", "bucket_name")
    monkeypatch.setenv("S3_SECURE", "false")


async def test_compute_input_data(
    app_with_db: None,
    aiopg_engine: aiopg.sa.engine.Engine,  # type: ignore
    async_client: httpx.AsyncClient,
    user_id: UserID,
    published_project: PublishedProject,
    fake_io_schema: dict[str, dict[str, str]],
    fake_io_data: dict[str, Any],
    create_simcore_file_id: Callable[[ProjectID, NodeID, str], SimcoreS3FileID],
    faker: Faker,
    mocker: MockerFixture,
    tasks_file_link_type: FileLinkType,
):
    sleeper_task: CompTaskAtDB = published_project.tasks[1]

    # set some fake inputs
    fake_inputs = {
        key: SimCoreFileLink(
            store=0,
            path=create_simcore_file_id(
                published_project.project.uuid, sleeper_task.node_id, faker.file_name()
            ),
        ).dict(by_alias=True, exclude_unset=True)
        if value_type["type"] == "data:*/*"
        else fake_io_data[key]
        for key, value_type in fake_io_schema.items()
    }
    await set_comp_task_inputs(
        aiopg_engine, sleeper_task.node_id, fake_io_schema, fake_inputs
    )
    # mock the get_value function so we can test it is called correctly
    def return_fake_input_value(*args, **kwargs):
        for value, value_type in zip(fake_inputs.values(), fake_io_schema.values()):
            if value_type["type"] == "data:*/*":
                yield parse_obj_as(AnyUrl, faker.url())
            else:
                yield value

    mocked_node_ports_get_value_fct = mocker.patch(
        "simcore_sdk.node_ports_v2.port.Port.get_value",
        autospec=True,
        side_effect=return_fake_input_value(),
    )
    computed_input_data = await compute_input_data(
        async_client._transport.app,
        user_id,
        published_project.project.uuid,
        sleeper_task.node_id,
        file_link_type=tasks_file_link_type,
    )
    mocked_node_ports_get_value_fct.assert_has_calls(
        [
            mock.call(mock.ANY, file_link_type=tasks_file_link_type)
            for n in fake_io_data.keys()
        ]
    )
    assert computed_input_data.keys() == fake_io_data.keys()


@pytest.fixture
def tasks_file_link_scheme(tasks_file_link_type: FileLinkType) -> tuple:
    if tasks_file_link_type == FileLinkType.S3:
        return ("s3", "s3a")
    if tasks_file_link_type == FileLinkType.PRESIGNED:
        return ("http", "https")
    assert False, "unknown file link type, need update of the fixture"


async def test_compute_output_data_schema(
    app_with_db: None,
    aiopg_engine: aiopg.sa.engine.Engine,  # type: ignore
    async_client: httpx.AsyncClient,
    user_id: UserID,
    published_project: PublishedProject,
    fake_io_schema: dict[str, dict[str, str]],
    tasks_file_link_type: FileLinkType,
    tasks_file_link_scheme: tuple,
    mocked_node_ports_filemanager_fcts: dict[str, mock.MagicMock],
):
    sleeper_task: CompTaskAtDB = published_project.tasks[1]
    # simulate pre-created file links
    no_outputs = {}
    await set_comp_task_outputs(
        aiopg_engine, sleeper_task.node_id, fake_io_schema, no_outputs
    )

    output_schema = await compute_output_data_schema(
        async_client._transport.app,
        user_id,
        published_project.project.uuid,
        sleeper_task.node_id,
        file_link_type=tasks_file_link_type,
    )
    for port_key, port_schema in fake_io_schema.items():
        assert port_key in output_schema
        assert output_schema[port_key]
        assert output_schema[port_key].required is True  # currently always true
        assert isinstance(output_schema[port_key], FilePortSchema) == port_schema[
            "type"
        ].startswith("data:")
        if isinstance(output_schema[port_key], FilePortSchema):
            file_port_schema = output_schema[port_key]
            assert isinstance(file_port_schema, FilePortSchema)
            assert file_port_schema.url.scheme in tasks_file_link_scheme
            if "fileToKeyMap" in port_schema:
                assert file_port_schema.mapping
            else:
                assert file_port_schema.mapping is None


@pytest.mark.parametrize("entry_exists_returns", [True, False])
async def test_clean_task_output_and_log_files_if_invalid(
    aiopg_engine: aiopg.sa.engine.Engine,  # type: ignore
    user_id: UserID,
    published_project: PublishedProject,
    mocked_node_ports_filemanager_fcts: dict[str, mock.MagicMock],
    create_simcore_file_id: Callable[[ProjectID, NodeID, str], SimcoreS3FileID],
    entry_exists_returns: bool,
    fake_io_schema: dict[str, dict[str, str]],
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
        key: SimCoreFileLink(
            store=0,
            path=create_simcore_file_id(
                published_project.project.uuid, sleeper_task.node_id, faker.file_name()
            ),
        ).dict(by_alias=True, exclude_unset=True)
        for key, value_type in fake_io_schema.items()
        if value_type["type"] == "data:*/*"
    }
    await set_comp_task_outputs(
        aiopg_engine, sleeper_task.node_id, fake_io_schema, fake_outputs
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
            store_id=0,
            s3_object=f"{published_project.project.uuid}/{sleeper_task.node_id}/{next(iter(fake_io_schema[key].get('fileToKeyMap', {key:key})))}",
        )
        for key in fake_outputs.keys()
    ] + [
        mock.call(
            user_id=user_id,
            store_id=0,
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


@pytest.mark.parametrize(
    "req_example", NodeRequirements.Config.schema_extra["examples"]
)
def test_node_requirements_correctly_convert_to_dask_resources(
    req_example: dict[str, Any]
):
    node_reqs = NodeRequirements(**req_example)
    assert node_reqs
    dask_resources = from_node_reqs_to_dask_resources(node_reqs)
    # all the dask resources shall be of type: RESOURCE_NAME: VALUE
    for resource_key, resource_value in dask_resources.items():
        assert isinstance(resource_key, str)
        assert isinstance(resource_value, (int, float, str, bool))
        assert resource_value is not None
