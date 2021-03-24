# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=too-many-arguments

import asyncio
import json
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Tuple

import np_helpers
import pytest
import sqlalchemy as sa
from pytest_simcore.helpers.rawdata_fakers import random_project, random_user
from simcore_postgres_database.storage_models import projects, users
from simcore_sdk.models.pipeline_models import ComputationalPipeline, ComputationalTask
from simcore_sdk.node_ports import node_config
from yarl import URL


@pytest.fixture
def user_id(postgres_engine: sa.engine.Engine) -> Iterable[int]:
    # inject user in db

    # NOTE: Ideally this (and next fixture) should be done via webserver API but at this point
    # in time, the webserver service would bring more dependencies to other services
    # which would turn this test too complex.

    # pylint: disable=no-value-for-parameter
    stmt = users.insert().values(**random_user(name="test")).returning(users.c.id)
    print(str(stmt))
    with postgres_engine.connect() as conn:
        result = conn.execute(stmt)
        [usr_id] = result.fetchone()

    yield usr_id

    with postgres_engine.connect() as conn:
        conn.execute(users.delete().where(users.c.id == usr_id))


@pytest.fixture
def project_id(user_id: int, postgres_engine: sa.engine.Engine) -> Iterable[str]:
    # inject project for user in db. This will give user_id, the full project's ownership

    # pylint: disable=no-value-for-parameter
    stmt = (
        projects.insert()
        .values(**random_project(prj_owner=user_id))
        .returning(projects.c.uuid)
    )
    print(str(stmt))
    with postgres_engine.connect() as conn:
        result = conn.execute(stmt)
        [prj_uuid] = result.fetchone()

    yield prj_uuid

    with postgres_engine.connect() as conn:
        conn.execute(projects.delete().where(projects.c.uuid == prj_uuid))


@pytest.fixture
def node_uuid() -> str:
    return str(uuid.uuid4())


@pytest.fixture
def s3_simcore_location() -> str:
    yield np_helpers.SIMCORE_STORE


@pytest.fixture
async def filemanager_cfg(
    loop: asyncio.events.AbstractEventLoop,
    storage_service: URL,
    devel_environ: Dict,
    user_id: str,
    bucket: str,
    postgres_db,  # waits for db and initializes it
) -> None:
    node_config.STORAGE_ENDPOINT = f"{storage_service.host}:{storage_service.port}"
    node_config.USER_ID = user_id
    node_config.BUCKET = bucket
    yield


@pytest.fixture
def create_valid_file_uuid(project_id: str, node_uuid: str) -> Callable:
    def create(file_path: Path, project: str = None, node: str = None):
        if project is None:
            project = project_id
        if node is None:
            node = node_uuid
        return np_helpers.file_uuid(file_path, project, node)

    return create


@pytest.fixture()
def default_configuration(
    node_ports_config,
    bucket,
    postgres_session: sa.orm.session.Session,
    default_configuration_file: Path,
    project_id,
    node_uuid,
) -> Dict:
    # prepare database with default configuration
    json_configuration = default_configuration_file.read_text()
    _create_new_pipeline(postgres_session, project_id)
    _set_configuration(postgres_session, project_id, node_uuid, json_configuration)
    config_dict = json.loads(json_configuration)
    node_config.NODE_UUID = str(node_uuid)
    node_config.PROJECT_ID = str(project_id)
    yield config_dict
    # teardown
    postgres_session.query(ComputationalTask).delete()
    postgres_session.query(ComputationalPipeline).delete()
    postgres_session.commit()


@pytest.fixture()
def node_link() -> Callable:
    def create_node_link(key: str) -> Dict[str, str]:
        return {"nodeUuid": "TEST_NODE_UUID", "output": key}

    yield create_node_link


@pytest.fixture()
def store_link(
    minio_service, bucket, create_valid_file_uuid, s3_simcore_location
) -> Callable:
    def create_store_link(
        file_path: Path, project_id: str = None, node_id: str = None
    ) -> Dict[str, str]:
        # upload the file to S3
        assert Path(file_path).exists()
        file_id = create_valid_file_uuid(file_path, project_id, node_id)
        # using the s3 client the path must be adapted
        # TODO: use the storage sdk instead
        s3_object = Path(project_id, node_id, Path(file_path).name).as_posix()
        minio_service.upload_file(bucket, s3_object, str(file_path))
        return {"store": s3_simcore_location, "path": file_id}

    yield create_store_link


@pytest.fixture(scope="function")
def special_configuration(
    node_ports_config: None,
    bucket: str,
    postgres_session: sa.orm.session.Session,
    empty_configuration_file: Path,
    project_id: str,
    node_uuid: str,
) -> Callable:
    def create_config(
        inputs: List[Tuple[str, str, Any]] = None,
        outputs: List[Tuple[str, str, Any]] = None,
        project_id: str = project_id,
        node_id: str = node_uuid,
    ) -> Tuple[Dict, str, str]:
        config_dict = json.loads(empty_configuration_file.read_text())
        _assign_config(config_dict, "inputs", inputs)
        _assign_config(config_dict, "outputs", outputs)
        project_id = _create_new_pipeline(postgres_session, project_id)
        node_uuid = _set_configuration(
            postgres_session, project_id, node_id, json.dumps(config_dict)
        )
        node_config.NODE_UUID = str(node_uuid)
        node_config.PROJECT_ID = str(project_id)
        return config_dict, project_id, node_uuid

    yield create_config
    # teardown
    postgres_session.query(ComputationalTask).delete()
    postgres_session.query(ComputationalPipeline).delete()
    postgres_session.commit()


@pytest.fixture(scope="function")
def special_2nodes_configuration(
    node_ports_config: None,
    bucket: str,
    postgres_session: sa.orm.session.Session,
    empty_configuration_file: Path,
    project_id: str,
    node_uuid: str,
):
    def create_config(
        prev_node_inputs: List[Tuple[str, str, Any]] = None,
        prev_node_outputs: List[Tuple[str, str, Any]] = None,
        inputs: List[Tuple[str, str, Any]] = None,
        outputs: List[Tuple[str, str, Any]] = None,
        project_id: str = project_id,
        previous_node_id: str = node_uuid,
        node_id: str = "asdasdadsa",
    ) -> Tuple[Dict, str, str]:
        _create_new_pipeline(postgres_session, project_id)

        # create previous node
        previous_config_dict = json.loads(empty_configuration_file.read_text())
        _assign_config(previous_config_dict, "inputs", prev_node_inputs)
        _assign_config(previous_config_dict, "outputs", prev_node_outputs)
        previous_node_uuid = _set_configuration(
            postgres_session,
            project_id,
            previous_node_id,
            json.dumps(previous_config_dict),
        )

        # create current node
        config_dict = json.loads(empty_configuration_file.read_text())
        _assign_config(config_dict, "inputs", inputs)
        _assign_config(config_dict, "outputs", outputs)
        # configure links if necessary
        str_config = json.dumps(config_dict)
        str_config = str_config.replace("TEST_NODE_UUID", str(previous_node_uuid))
        config_dict = json.loads(str_config)
        node_uuid = _set_configuration(
            postgres_session, project_id, node_id, str_config
        )
        node_config.NODE_UUID = str(node_uuid)
        node_config.PROJECT_ID = str(project_id)
        return config_dict, project_id, node_uuid

    yield create_config
    # teardown
    postgres_session.query(ComputationalTask).delete()
    postgres_session.query(ComputationalPipeline).delete()
    postgres_session.commit()


def _create_new_pipeline(postgres_session: sa.orm.session.Session, project: str) -> str:
    # pylint: disable=no-member
    new_Pipeline = ComputationalPipeline(project_id=project)
    postgres_session.add(new_Pipeline)
    postgres_session.commit()
    return new_Pipeline.project_id


def _set_configuration(
    postgres_session: sa.orm.session.Session,
    project_id: str,
    node_id: str,
    json_configuration: str,
) -> str:
    node_uuid = node_id
    json_configuration = json_configuration.replace("SIMCORE_NODE_UUID", str(node_uuid))
    configuration = json.loads(json_configuration)

    new_Node = ComputationalTask(
        project_id=project_id,
        node_id=node_uuid,
        schema=configuration["schema"],
        inputs=configuration["inputs"],
        outputs=configuration["outputs"],
        run_hash=configuration["run_hash"],
    )
    postgres_session.add(new_Node)
    postgres_session.commit()
    return node_uuid


def _assign_config(
    config_dict: dict, port_type: str, entries: List[Tuple[str, str, Any]]
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
        if not entry[2] is None:
            config_dict[port_type].update({entry[0]: entry[2]})
