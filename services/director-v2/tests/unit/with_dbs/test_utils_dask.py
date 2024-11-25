# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=no-value-for-parameter
# pylint:disable=protected-access
# pylint:disable=too-many-arguments
# pylint:disable=no-name-in-module


from collections.abc import Callable
from copy import deepcopy
from random import choice
from typing import Any
from unittest import mock

import aiopg
import aiopg.sa
import pytest
from _helpers import PublishedProject, set_comp_task_inputs, set_comp_task_outputs
from dask_task_models_library.container_tasks.io import (
    FilePortSchema,
    FileUrl,
    TaskOutputData,
)
from dask_task_models_library.container_tasks.protocol import (
    ContainerEnvsDict,
    ContainerLabelsDict,
)
from distributed import SpecCluster
from faker import Faker
from fastapi import FastAPI
from models_library.api_schemas_directorv2.services import NodeRequirements
from models_library.api_schemas_storage import FileUploadLinks, FileUploadSchema
from models_library.clusters import ClusterID
from models_library.docker import to_simcore_runtime_docker_label_key
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID, SimCoreFileLink, SimcoreS3FileID
from models_library.users import UserID
from pydantic import ByteSize, TypeAdapter
from pydantic.networks import AnyUrl
from pytest_mock.plugin import MockerFixture
from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_sdk.node_ports_v2 import FileLinkType
from simcore_service_director_v2.constants import UNDEFINED_DOCKER_LABEL
from simcore_service_director_v2.models.comp_runs import RunMetadataDict
from simcore_service_director_v2.models.comp_tasks import CompTaskAtDB
from simcore_service_director_v2.modules.dask_clients_pool import DaskClientsPool
from simcore_service_director_v2.utils.dask import (
    _LOGS_FILE_NAME,
    _to_human_readable_resource_values,
    check_if_cluster_is_able_to_run_pipeline,
    clean_task_output_and_log_files_if_invalid,
    compute_input_data,
    compute_output_data_schema,
    compute_task_envs,
    compute_task_labels,
    create_node_ports,
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
                        TypeAdapter(AnyUrl).validate_python(
                            f"{URL(faker.uri()).with_scheme(choice(tasks_file_link_scheme))}",  # noqa: S311
                        )
                    ],
                    chunk_size=TypeAdapter(ByteSize).validate_python("5GiB"),
                    links=FileUploadLinks(
                        abort_upload=TypeAdapter(AnyUrl).validate_python("https://www.fakeabort.com"),
                        complete_upload=TypeAdapter(AnyUrl).validate_python(
                            "https://www.fakecomplete.com"
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
        f"pytest_io_key_{faker.pystr()}": choice(  # noqa: S311
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
        ).model_dump(by_alias=True, exclude_unset=True)

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
        key: (
            {
                "url": faker.url(),
                "file_mapping": (
                    next(iter(fake_io_schema[key]["fileToKeyMap"]))
                    if "fileToKeyMap" in fake_io_schema[key]
                    else None
                ),
            }
            if fake_io_schema[key]["type"] == "data:*/*"
            else value
        )
        for key, value in fake_io_data.items()
    }
    data = TypeAdapter(TaskOutputData).validate_python(converted_data)
    assert data
    return data


async def test_parse_output_data(
    aiopg_engine: aiopg.sa.engine.Engine,
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
def _app_config_with_db(
    mock_env: EnvVarsDict,
    monkeypatch: pytest.MonkeyPatch,
    postgres_host_config: dict[str, str],
    faker: Faker,
):
    monkeypatch.setenv("R_CLONE_PROVIDER", "MINIO")
    monkeypatch.setenv("S3_ENDPOINT", faker.url())
    monkeypatch.setenv("S3_ACCESS_KEY", faker.pystr())
    monkeypatch.setenv("S3_REGION", faker.pystr())
    monkeypatch.setenv("S3_SECRET_KEY", faker.pystr())
    monkeypatch.setenv("S3_BUCKET_NAME", faker.pystr())


async def test_compute_input_data(
    _app_config_with_db: None,
    aiopg_engine: aiopg.sa.engine.Engine,
    initialized_app: FastAPI,
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
        key: (
            SimCoreFileLink(
                store=0,
                path=create_simcore_file_id(
                    published_project.project.uuid,
                    sleeper_task.node_id,
                    faker.file_name(),
                ),
            ).model_dump(by_alias=True, exclude_unset=True)
            if value_type["type"] == "data:*/*"
            else fake_io_data[key]
        )
        for key, value_type in fake_io_schema.items()
    }
    await set_comp_task_inputs(
        aiopg_engine, sleeper_task.node_id, fake_io_schema, fake_inputs
    )

    # mock the get_value function so we can test it is called correctly
    def return_fake_input_value(*args, **kwargs):
        for value, value_type in zip(
            fake_inputs.values(), fake_io_schema.values(), strict=True
        ):
            if value_type["type"] == "data:*/*":
                yield TypeAdapter(AnyUrl).validate_python(faker.url())
            else:
                yield value

    mocked_node_ports_get_value_fct = mocker.patch(
        "simcore_sdk.node_ports_v2.port.Port.get_value",
        autospec=True,
        side_effect=return_fake_input_value(),
    )
    node_ports = await create_node_ports(
        db_engine=initialized_app.state.engine,
        user_id=user_id,
        project_id=published_project.project.uuid,
        node_id=sleeper_task.node_id,
    )
    computed_input_data = await compute_input_data(
        project_id=published_project.project.uuid,
        node_id=sleeper_task.node_id,
        file_link_type=tasks_file_link_type,
        node_ports=node_ports,
    )
    mocked_node_ports_get_value_fct.assert_has_calls(
        [mock.call(mock.ANY, file_link_type=tasks_file_link_type) for n in fake_io_data]
    )
    assert computed_input_data.keys() == fake_io_data.keys()


@pytest.fixture
def tasks_file_link_scheme(tasks_file_link_type: FileLinkType) -> tuple:
    if tasks_file_link_type == FileLinkType.S3:
        return ("s3", "s3a")
    if tasks_file_link_type == FileLinkType.PRESIGNED:
        return ("http", "https")
    pytest.fail("unknown file link type, need update of the fixture")
    return ("thankspylint",)


async def test_compute_output_data_schema(
    _app_config_with_db: None,
    aiopg_engine: aiopg.sa.engine.Engine,
    initialized_app: FastAPI,
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

    node_ports = await create_node_ports(
        db_engine=initialized_app.state.engine,
        user_id=user_id,
        project_id=published_project.project.uuid,
        node_id=sleeper_task.node_id,
    )

    output_schema = await compute_output_data_schema(
        user_id=user_id,
        project_id=published_project.project.uuid,
        node_id=sleeper_task.node_id,
        file_link_type=tasks_file_link_type,
        node_ports=node_ports,
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
    aiopg_engine: aiopg.sa.engine.Engine,
    user_id: UserID,
    published_project: PublishedProject,
    mocked_node_ports_filemanager_fcts: dict[str, mock.MagicMock],
    create_simcore_file_id: Callable[[ProjectID, NodeID, str], SimcoreS3FileID],
    entry_exists_returns: bool,  # noqa: FBT001
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
        ).model_dump(by_alias=True, exclude_unset=True)
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
        for key in fake_outputs
    ] + [
        mock.call(
            user_id=user_id,
            store_id=0,
            s3_object=f"{published_project.project.uuid}/{sleeper_task.node_id}/{_LOGS_FILE_NAME}",
        )
    ]

    def _add_is_directory(entry: mock._Call) -> mock._Call:  # noqa: SLF001
        new_kwargs: dict[str, Any] = deepcopy(entry.kwargs)
        new_kwargs["is_directory"] = False
        return mock.call(**new_kwargs)

    mocked_node_ports_filemanager_fcts["entry_exists"].assert_has_calls(
        [_add_is_directory(x) for x in expected_calls]
    )
    if entry_exists_returns:
        mocked_node_ports_filemanager_fcts["delete_file"].assert_not_called()
    else:
        mocked_node_ports_filemanager_fcts["delete_file"].assert_has_calls(
            expected_calls
        )


@pytest.mark.parametrize(
    "req_example", NodeRequirements.model_config["json_schema_extra"]["examples"]
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
        assert isinstance(resource_value, int | float | str | bool)
        assert resource_value is not None


@pytest.mark.parametrize(
    "input_resources, expected_human_readable_resources",
    [
        ({}, {}),
        (
            {"CPU": 2.1, "RAM": 1024, "VRAM": 2097152},
            {"CPU": 2.1, "RAM": "1.0KiB", "VRAM": "2.0MiB"},
        ),
    ],
    ids=str,
)
def test__to_human_readable_resource_values(
    input_resources: dict[str, Any], expected_human_readable_resources: dict[str, Any]
):
    assert (
        _to_human_readable_resource_values(input_resources)
        == expected_human_readable_resources
    )


@pytest.fixture
def cluster_id(faker: Faker) -> ClusterID:
    return faker.pyint(min_value=0)


@pytest.fixture
def _app_config_with_dask_client(
    _app_config_with_db: None,
    dask_spec_local_cluster: SpecCluster,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("COMPUTATIONAL_BACKEND_DASK_CLIENT_ENABLED", "1")
    monkeypatch.setenv(
        "COMPUTATIONAL_BACKEND_DEFAULT_CLUSTER_URL",
        dask_spec_local_cluster.scheduler_address,
    )


async def test_check_if_cluster_is_able_to_run_pipeline(
    _app_config_with_dask_client: None,
    project_id: ProjectID,
    node_id: NodeID,
    cluster_id: ClusterID,
    published_project: PublishedProject,
    initialized_app: FastAPI,
):
    sleeper_task: CompTaskAtDB = published_project.tasks[1]
    dask_scheduler_settings = (
        initialized_app.state.settings.DIRECTOR_V2_COMPUTATIONAL_BACKEND
    )
    default_cluster = dask_scheduler_settings.default_cluster
    dask_clients_pool = DaskClientsPool.instance(initialized_app)
    async with dask_clients_pool.acquire(default_cluster) as dask_client:
        check_if_cluster_is_able_to_run_pipeline(
            project_id=project_id,
            node_id=node_id,
            cluster_id=cluster_id,
            node_image=sleeper_task.image,
            scheduler_info=dask_client.backend.client.scheduler_info(),
            task_resources={},
        )


@pytest.mark.parametrize(
    "run_metadata, expected_additional_task_labels",
    [
        (
            {},
            {
                f"{to_simcore_runtime_docker_label_key('product-name')}": UNDEFINED_DOCKER_LABEL,
                f"{to_simcore_runtime_docker_label_key('simcore-user-agent')}": UNDEFINED_DOCKER_LABEL,
            },
        ),
        (
            {
                f"{to_simcore_runtime_docker_label_key('product-name')}": "the awesome osparc",
                "some-crazy-additional-label": "with awesome value",
            },
            {
                f"{to_simcore_runtime_docker_label_key('product-name')}": "the awesome osparc",
                f"{to_simcore_runtime_docker_label_key('simcore-user-agent')}": UNDEFINED_DOCKER_LABEL,
                "some-crazy-additional-label": "with awesome value",
            },
        ),
    ],
)
async def test_compute_task_labels(
    _app_config_with_db: None,
    published_project: PublishedProject,
    user_id: UserID,
    project_id: ProjectID,
    node_id: NodeID,
    run_metadata: RunMetadataDict,
    expected_additional_task_labels: ContainerLabelsDict,
    initialized_app: FastAPI,
):
    sleeper_task = published_project.tasks[1]
    assert sleeper_task.image
    assert sleeper_task.image.node_requirements
    task_labels = compute_task_labels(
        user_id=user_id,
        project_id=project_id,
        node_id=node_id,
        run_metadata=run_metadata,
        node_requirements=sleeper_task.image.node_requirements,
    )
    expected_task_labels = {
        f"{to_simcore_runtime_docker_label_key('user-id')}": f"{user_id}",
        f"{to_simcore_runtime_docker_label_key('project-id')}": f"{project_id}",
        f"{to_simcore_runtime_docker_label_key('node-id')}": f"{node_id}",
        f"{to_simcore_runtime_docker_label_key('swarm-stack-name')}": f"{UNDEFINED_DOCKER_LABEL}",
        f"{to_simcore_runtime_docker_label_key('cpu-limit')}": f"{sleeper_task.image.node_requirements.cpu}",
        f"{to_simcore_runtime_docker_label_key('memory-limit')}": f"{sleeper_task.image.node_requirements.ram}",
    } | expected_additional_task_labels
    assert task_labels == expected_task_labels


@pytest.mark.parametrize(
    "run_metadata",
    [
        {"product_name": "some amazing product name"},
    ],
)
@pytest.mark.parametrize(
    "input_task_envs, expected_computed_task_envs",
    [
        pytest.param({}, {}, id="empty envs"),
        pytest.param(
            {"SOME_FAKE_ENV": "this is my fake value"},
            {"SOME_FAKE_ENV": "this is my fake value"},
            id="standard env",
        ),
        pytest.param(
            {"SOME_FAKE_ENV": "this is my $OSPARC_VARIABLE_PRODUCT_NAME value"},
            {"SOME_FAKE_ENV": "this is my some amazing product name value"},
            id="substituable env",
        ),
    ],
)
async def test_compute_task_envs(
    _app_config_with_db: None,
    published_project: PublishedProject,
    initialized_app: FastAPI,
    run_metadata: RunMetadataDict,
    input_task_envs: ContainerEnvsDict,
    expected_computed_task_envs: ContainerEnvsDict,
):
    sleeper_task: CompTaskAtDB = published_project.tasks[1]
    sleeper_task.image.envs = input_task_envs
    assert published_project.project.prj_owner is not None
    task_envs = await compute_task_envs(
        initialized_app,
        user_id=published_project.project.prj_owner,
        project_id=published_project.project.uuid,
        node_id=sleeper_task.node_id,
        node_image=sleeper_task.image,
        metadata=run_metadata,
    )
    assert task_envs == expected_computed_task_envs
