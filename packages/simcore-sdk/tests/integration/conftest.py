# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=too-many-arguments

import json
import urllib.parse
from collections.abc import Awaitable, Callable, Iterable, Iterator
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
import sqlalchemy as sa
from aiohttp import ClientSession
from models_library.api_schemas_storage import FileUploadSchema
from models_library.generics import Envelope
from models_library.projects_nodes_io import LocationID, NodeIDStr, SimcoreS3FileID
from models_library.users import UserID
from pydantic import TypeAdapter
from pytest_simcore.helpers.faker_factories import random_project, random_user
from settings_library.aws_s3_cli import AwsS3CliSettings
from settings_library.r_clone import RCloneSettings, S3Provider
from settings_library.s3 import S3Settings
from simcore_postgres_database.models.comp_pipeline import comp_pipeline
from simcore_postgres_database.models.comp_tasks import comp_tasks
from simcore_postgres_database.models.file_meta_data import file_meta_data
from simcore_postgres_database.models.projects import projects
from simcore_postgres_database.models.users import users
from simcore_sdk.node_ports_common.aws_s3_cli import is_aws_s3_cli_available
from simcore_sdk.node_ports_common.r_clone import is_r_clone_available
from yarl import URL


@pytest.fixture
def user_id(postgres_db: sa.engine.Engine) -> Iterable[UserID]:
    # inject user in db

    # NOTE: Ideally this (and next fixture) should be done via webserver API but at this point
    # in time, the webserver service would bring more dependencies to other services
    # which would turn this test too complex.

    # pylint: disable=no-value-for-parameter
    with postgres_db.connect() as conn:
        result = conn.execute(
            users.insert().values(**random_user(name="test")).returning(users.c.id)
        )
        row = result.first()
        assert row
        usr_id = row[users.c.id]

    yield usr_id

    with postgres_db.connect() as conn:
        conn.execute(users.delete().where(users.c.id == usr_id))


@pytest.fixture
def project_id(user_id: int, postgres_db: sa.engine.Engine) -> Iterable[str]:
    # inject project for user in db. This will give user_id, the full project's ownership

    # pylint: disable=no-value-for-parameter
    stmt = (
        projects.insert()
        .values(**random_project(prj_owner=user_id))
        .returning(projects.c.uuid)
    )
    print(f"{stmt}")
    with postgres_db.connect() as conn:
        result = conn.execute(stmt)
        row = result.first()
        assert row
        prj_uuid = row[projects.c.uuid]

    yield prj_uuid

    with postgres_db.connect() as conn:
        conn.execute(projects.delete().where(projects.c.uuid == prj_uuid))


@pytest.fixture(scope="module")
def node_uuid() -> NodeIDStr:
    return TypeAdapter(NodeIDStr).validate_python(f"{uuid4()}")


@pytest.fixture(scope="session")
def s3_simcore_location() -> LocationID:
    return 0


@pytest.fixture
def create_valid_file_uuid(
    project_id: str, node_uuid: str
) -> Callable[[str, Path], SimcoreS3FileID]:
    def _create(key: str, file_path: Path) -> SimcoreS3FileID:
        clean_path = Path(f"{project_id}/{node_uuid}/{key}/{file_path.name}")
        return TypeAdapter(SimcoreS3FileID).validate_python(f"{clean_path}")

    return _create


@pytest.fixture()
def default_configuration(
    node_ports_config: None,
    create_pipeline: Callable[[str], str],
    create_task: Callable[..., str],
    default_configuration_file: Path,
    project_id: str,
    node_uuid: str,
) -> dict[str, Any]:
    # prepare database with default configuration
    json_configuration = default_configuration_file.read_text()
    create_pipeline(project_id)
    return _set_configuration(create_task, project_id, node_uuid, json_configuration)


@pytest.fixture()
def create_node_link() -> Callable[[str], dict[str, str]]:
    def _create(key: str) -> dict[str, str]:
        return {"nodeUuid": "TEST_NODE_UUID", "output": key}

    return _create


@pytest.fixture()
def create_store_link(
    create_valid_file_uuid: Callable[[str, Path], SimcoreS3FileID],
    s3_simcore_location: LocationID,
    user_id: int,
    project_id: str,
    node_uuid: str,
    storage_service: URL,  # packages/pytest-simcore/src/pytest_simcore/simcore_storage_service.py
) -> Callable[[Path], Awaitable[dict[str, Any]]]:
    async def _create(file_path: Path) -> dict[str, Any]:
        file_path = Path(file_path)
        assert file_path.exists()

        file_id = create_valid_file_uuid("", file_path)
        url = URL(
            f"{storage_service}/v0/locations/{s3_simcore_location}/files/{urllib.parse.quote(file_id, safe='')}"
        ).with_query(user_id=user_id, file_size=0)
        async with ClientSession() as session:
            async with session.put(url) as resp:
                resp.raise_for_status()
                presigned_links_enveloped = Envelope[FileUploadSchema].model_validate(
                    await resp.json()
                )
            assert presigned_links_enveloped.data
            assert len(presigned_links_enveloped.data.urls) == 1
            link = presigned_links_enveloped.data.urls[0]
            assert link

            # Upload using the link
            extra_hdr = {
                "Content-Length": f"{file_path.stat().st_size}",
                "Content-Type": "application/binary",
            }
            async with session.put(
                f"{link}", data=file_path.read_bytes(), headers=extra_hdr
            ) as resp:
                resp.raise_for_status()

        # NOTE: that at this point, S3 and pg have some data that is NOT cleaned up
        return {"store": s3_simcore_location, "path": file_id}

    return _create


@pytest.fixture()
def create_special_configuration(
    node_ports_config: None,
    create_pipeline: Callable[[str], str],
    create_task: Callable[..., str],
    empty_configuration_file: Path,
    project_id: str,
    node_uuid: str,
) -> Callable:
    def _create(
        inputs: list[tuple[str, str, Any]] | None = None,
        outputs: list[tuple[str, str, Any]] | None = None,
        project_id: str = project_id,
        node_id: str = node_uuid,
    ) -> tuple[dict, str, str]:
        config_dict = json.loads(empty_configuration_file.read_text())
        _assign_config(config_dict, "inputs", inputs if inputs else [])
        _assign_config(config_dict, "outputs", outputs if outputs else [])
        project_id = create_pipeline(project_id)
        config_dict = _set_configuration(
            create_task, project_id, node_id, json.dumps(config_dict)
        )
        return config_dict, project_id, node_uuid

    return _create


@pytest.fixture()
def create_2nodes_configuration(
    node_ports_config: None,
    create_pipeline: Callable[[str], str],
    create_task: Callable[..., str],
    empty_configuration_file: Path,
) -> Callable:
    def _create(
        prev_node_inputs: list[tuple[str, str, Any]],
        prev_node_outputs: list[tuple[str, str, Any]],
        inputs: list[tuple[str, str, Any]],
        outputs: list[tuple[str, str, Any]],
        project_id: str,
        previous_node_id: str,
        node_id: str,
    ) -> tuple[dict, str, str]:
        create_pipeline(project_id)

        # create previous node
        previous_config_dict = json.loads(empty_configuration_file.read_text())
        _assign_config(
            previous_config_dict, "inputs", prev_node_inputs if prev_node_inputs else []
        )
        _assign_config(
            previous_config_dict,
            "outputs",
            prev_node_outputs if prev_node_outputs else [],
        )
        previous_config_dict = _set_configuration(
            create_task,
            project_id,
            previous_node_id,
            json.dumps(previous_config_dict),
        )

        # create current node
        config_dict = json.loads(empty_configuration_file.read_text())
        _assign_config(config_dict, "inputs", inputs if inputs else [])
        _assign_config(config_dict, "outputs", outputs if outputs else [])
        # configure links if necessary
        str_config = json.dumps(config_dict)
        str_config = str_config.replace("TEST_NODE_UUID", previous_node_id)
        config_dict = _set_configuration(create_task, project_id, node_id, str_config)
        return config_dict, project_id, node_id

    return _create


@pytest.fixture
def create_pipeline(postgres_db: sa.engine.Engine) -> Iterator[Callable[[str], str]]:
    created_pipeline_ids: list[str] = []

    def _create(project_id: str) -> str:
        with postgres_db.connect() as conn:
            result = conn.execute(
                comp_pipeline.insert()  # pylint: disable=no-value-for-parameter
                .values(project_id=project_id)
                .returning(comp_pipeline.c.project_id)
            )
            row = result.first()
            assert row
            new_pipeline_id = row[comp_pipeline.c.project_id]
        created_pipeline_ids.append(f"{new_pipeline_id}")
        return new_pipeline_id

    yield _create

    # cleanup
    with postgres_db.connect() as conn:
        conn.execute(
            comp_pipeline.delete().where(  # pylint: disable=no-value-for-parameter
                comp_pipeline.c.project_id.in_(created_pipeline_ids)
            )
        )


@pytest.fixture
def create_task(postgres_db: sa.engine.Engine) -> Iterator[Callable[..., str]]:
    created_task_ids: list[int] = []

    def _create(project_id: str, node_uuid: str, **overrides) -> str:
        task_config = {
            "project_id": project_id,
            "node_id": node_uuid,
        }
        task_config.update(**overrides)
        with postgres_db.connect() as conn:
            result = conn.execute(
                comp_tasks.insert()  # pylint: disable=no-value-for-parameter
                .values(**task_config)
                .returning(comp_tasks.c.task_id)
            )
            row = result.first()
            assert row
            new_task_id = row[comp_tasks.c.task_id]
        created_task_ids.append(new_task_id)
        return node_uuid

    yield _create

    # cleanup
    with postgres_db.connect() as conn:
        conn.execute(
            comp_tasks.delete().where(  # pylint: disable=no-value-for-parameter
                comp_tasks.c.task_id.in_(created_task_ids)
            )
        )


def _set_configuration(
    task: Callable[..., str],
    project_id: str,
    node_id: str,
    json_configuration: str,
) -> dict[str, Any]:
    json_configuration = json_configuration.replace("SIMCORE_NODE_UUID", str(node_id))
    configuration = json.loads(json_configuration)
    task(project_id, node_id, **configuration)
    return configuration


def _assign_config(
    config_dict: dict, port_type: str, entries: list[tuple[str, str, Any]]
):
    if entries is None:
        return
    for entry in entries:
        config_dict["schema"][port_type].update(
            {
                entry[0]: {
                    "label": "some label",
                    "description": "some description",
                    "displayOrder": 2,
                    "type": entry[1],
                }
            }
        )
        if entry[2] is not None:
            config_dict[port_type].update({entry[0]: entry[2]})


@pytest.fixture
async def r_clone_settings_factory(
    minio_s3_settings: S3Settings, storage_service: URL
) -> Awaitable[RCloneSettings]:
    async def _factory() -> RCloneSettings:
        settings = RCloneSettings(
            R_CLONE_S3=minio_s3_settings, R_CLONE_PROVIDER=S3Provider.MINIO
        )
        if not await is_r_clone_available(settings):
            pytest.skip("rclone not installed")

        return settings

    return _factory()


@pytest.fixture
async def aws_s3_cli_settings_factory(
    minio_s3_settings: S3Settings, storage_service: URL
) -> Awaitable[AwsS3CliSettings]:
    async def _factory() -> AwsS3CliSettings:
        settings = AwsS3CliSettings(AWS_S3_CLI_S3=minio_s3_settings)
        if not await is_aws_s3_cli_available(settings):
            pytest.skip("aws cli not installed")

        return settings

    return _factory()


@pytest.fixture
async def r_clone_settings(
    r_clone_settings_factory: Awaitable[RCloneSettings],
) -> RCloneSettings:
    return await r_clone_settings_factory


@pytest.fixture
async def aws_s3_cli_settings(
    aws_s3_cli_settings_factory: Awaitable[AwsS3CliSettings],
) -> AwsS3CliSettings:
    return await aws_s3_cli_settings_factory


@pytest.fixture
def cleanup_file_meta_data(postgres_db: sa.engine.Engine) -> Iterator[None]:
    yield None
    with postgres_db.connect() as conn:
        conn.execute(file_meta_data.delete())


@pytest.fixture
def node_ports_config(
    node_ports_config,
    with_bucket_versioning_enabled: str,
    simcore_services_ready,
    cleanup_file_meta_data: None,
) -> None:
    return None
