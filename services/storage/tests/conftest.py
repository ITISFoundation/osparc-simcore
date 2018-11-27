# pylint:disable=wildcard-import
# pylint:disable=unused-import
# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import asyncio
import os
import subprocess
import sys
import uuid
from collections import namedtuple
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from random import randrange

import pytest
from aiopg.sa import create_engine

import simcore_service_storage
import utils
from simcore_service_storage.datcore_wrapper import DatcoreWrapper
from simcore_service_storage.dsm import DataStorageManager
from simcore_service_storage.models import FileMetaData
from simcore_service_storage.s3 import (DATCORE_ID, DATCORE_STR, SIMCORE_S3_ID,
                                        SIMCORE_S3_STR)
from utils import ACCESS_KEY, BUCKET_NAME, DATABASE, PASS, SECRET_KEY, USER



@pytest.fixture(scope='session')
def here():
    return Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent


@pytest.fixture(scope='session')
def package_dir(here):
    dirpath = Path(simcore_service_storage.__file__).parent
    assert dirpath.exists()
    return dirpath


@pytest.fixture(scope='session')
def osparc_simcore_root_dir(here):
    root_dir = here.parent.parent.parent
    assert root_dir.exists() and any(root_dir.glob("services")), "Is this service within osparc-simcore repo?"
    return root_dir


@pytest.fixture(scope='session')
def osparc_api_specs_dir(osparc_simcore_root_dir):
    dirpath = osparc_simcore_root_dir / "api" / "specs"
    assert dirpath.exists()
    return dirpath

@pytest.fixture(scope='session')
def python27_exec(osparc_simcore_root_dir, tmpdir_factory, here):
    # Assumes already created with make .venv27
    venv27 = osparc_simcore_root_dir / ".venv27"

    if not venv27.exists():
        # create its own virtualenv
        venv27 = tmpdir_factory.mktemp("virtualenv") / ".venv27"
        # TODO: how to split in command safely?
        cmd = "virtualenv --python=python2 %s" % (venv27)
        assert subprocess.check_call(
            cmd.split()) == 0, "Unable to run %s" % cmd

        # installs python2 requirements
        pip_exec = venv27 / "bin" / "pip"
        assert pip_exec.exists()
        requirements_py2 = here.parent / "requirements/py27.txt"
        cmd = "{} install -r {}".format(pip_exec, requirements_py2)
        assert subprocess.check_call(
            cmd.split()) == 0, "Unable to run %s" % cmd

    python27_exec = venv27 / "bin" / "python2.7"
    assert python27_exec.exists()
    return python27_exec


@pytest.fixture(scope='session')
def python27_path(python27_exec):
    return Path(python27_exec).parent.parent
    # Assumes already created with make .venv27


@pytest.fixture(scope='session')
def docker_compose_file(here):
    """ Overrides pytest-docker fixture
    """
    old = os.environ.copy()

    # docker-compose reads these environs
    os.environ['POSTGRES_DB'] = DATABASE
    os.environ['POSTGRES_USER'] = USER
    os.environ['POSTGRES_PASSWORD'] = PASS
    os.environ['POSTGRES_ENDPOINT'] = "FOO"  # TODO: update config schema!!
    os.environ['MINIO_ACCESS_KEY'] = ACCESS_KEY
    os.environ['MINIO_SECRET_KEY'] = SECRET_KEY

    dc_path = here / 'docker-compose.yml'

    assert dc_path.exists()
    yield str(dc_path)

    os.environ = old


@pytest.fixture(scope='session')
def postgres_service(docker_services, docker_ip):
    url = 'postgresql://{user}:{password}@{host}:{port}/{database}'.format(
        user=USER,
        password=PASS,
        database=DATABASE,
        host=docker_ip,
        port=docker_services.port_for('postgres', 5432),
    )

    # Wait until service is responsive.
    docker_services.wait_until_responsive(
        check=lambda: utils.is_postgres_responsive(url),
        timeout=30.0,
        pause=0.1,
    )

    postgres_service = {
        'user': USER,
        'password': PASS,
        'database': DATABASE,
        'host': docker_ip,
        'port': docker_services.port_for('postgres', 5432)
    }

    return postgres_service


@pytest.fixture(scope='session')
def postgres_service_url(postgres_service, docker_services, docker_ip):
    postgres_service_url = 'postgresql://{user}:{password}@{host}:{port}/{database}'.format(
        user=USER,
        password=PASS,
        database=DATABASE,
        host=docker_ip,
        port=docker_services.port_for('postgres', 5432),
    )

    return postgres_service_url


@pytest.fixture(scope='function')
async def postgres_engine(loop, postgres_service_url):
    postgres_engine = await create_engine(postgres_service_url)

    yield postgres_engine

    if postgres_engine:
        postgres_engine.close()
        await postgres_engine.wait_closed()


@pytest.fixture(scope='session')
def minio_service(docker_services, docker_ip):

   # Build URL to service listening on random port.
    url = 'http://%s:%d/' % (
        docker_ip,
        docker_services.port_for('minio', 9000),
    )

    # Wait until service is responsive.
    docker_services.wait_until_responsive(
        check=lambda: utils.is_responsive(url, 403),
        timeout=30.0,
        pause=0.1,
    )

    return {
        'endpoint': '{ip}:{port}'.format(ip=docker_ip, port=docker_services.port_for('minio', 9000)),
        'access_key': ACCESS_KEY,
        'secret_key': SECRET_KEY,
        'bucket_name': BUCKET_NAME,
    }


@pytest.fixture(scope="module")
def s3_client(minio_service):
    from s3wrapper.s3_client import S3Client

    s3_client = S3Client(
        endpoint=minio_service['endpoint'], access_key=minio_service["access_key"], secret_key=minio_service["secret_key"])
    return s3_client


@pytest.fixture(scope="function")
def mock_files_factory(tmpdir_factory):
    def _create_files(count):
        filepaths = []
        for _i in range(count):
            name = str(uuid.uuid4())
            filepath = os.path.normpath(
                str(tmpdir_factory.mktemp('data').join(name + ".txt")))
            with open(filepath, 'w') as fout:
                fout.write("Hello world\n")
            filepaths.append(filepath)

        return filepaths
    return _create_files


@pytest.fixture(scope="function")
def dsm_mockup_db(postgres_service_url, s3_client, mock_files_factory):
    # db
    utils.create_tables(url=postgres_service_url)

    # s3 client
    bucket_name = BUCKET_NAME
    s3_client.create_bucket(bucket_name, delete_contents_if_exists=True)

    # TODO: use pip install Faker
    users = ['alice', 'bob', 'chuck', 'dennis']

    projects = ['astronomy', 'biology', 'chemistry',
                'dermatology', 'economics', 'futurology', 'geology']
    location = SIMCORE_S3_STR

    nodes = ['alpha', 'beta', 'gamma', 'delta']

    N = 100
    files = mock_files_factory(count=N)
    counter = 0
    data = {}
    for _file in files:
        idx = randrange(len(users))
        user_name = users[idx]
        user_id = idx + 10
        idx = randrange(len(projects))
        project_name = projects[idx]
        project_id = idx + 100
        idx = randrange(len(nodes))
        node = nodes[idx]
        node_id = idx + 10000
        file_name = str(counter)
        object_name = Path(str(project_id), str(
            node_id), str(counter)).as_posix()
        file_uuid = Path(object_name).as_posix()

        assert s3_client.upload_file(bucket_name, object_name, _file)

        d = {'file_uuid': file_uuid,
             'location_id': "0",
             'location': location,
             'bucket_name': bucket_name,
             'object_name': object_name,
             'project_id': str(project_id),
             'project_name': project_name,
             'node_id': str(node_id),
             'node_name': node,
             'file_name': file_name,
             'user_id': str(user_id),
             'user_name': user_name
             }

        counter = counter + 1

        data[object_name] = FileMetaData(**d)

        # pylint: disable=no-member
        utils.insert_metadata(postgres_service_url,
                              data[object_name])

    total_count = 0
    for _obj in s3_client.list_objects_v2(bucket_name, recursive=True):
        total_count = total_count + 1

    assert total_count == N
    yield data

    # s3 client
    s3_client.remove_bucket(bucket_name, delete_contents=True)

    # db
    utils.drop_tables(url=postgres_service_url)


@pytest.fixture(scope="function")
async def datcore_testbucket(loop, python27_exec, mock_files_factory):
    # TODO: what if I do not have an app to the the config from?
    api_token = os.environ.get("BF_API_KEY", "none")
    api_secret = os.environ.get("BF_API_SECRET", "none")

    pool = ThreadPoolExecutor(2)
    dcw = DatcoreWrapper(api_token, api_secret, python27_exec, loop, pool)

    await dcw.create_test_dataset(BUCKET_NAME)

    tmp_files = mock_files_factory(2)
    for f in tmp_files:
        await dcw.upload_file(BUCKET_NAME, os.path.normpath(f))

    ready = False
    counter = 0
    while not ready and counter < 5:
        data = await dcw.list_files()
        ready = len(data) == 2
        await asyncio.sleep(10)
        counter = counter + 1

    yield BUCKET_NAME

    await dcw.delete_test_dataset(BUCKET_NAME)


@pytest.fixture(scope="function")
def dsm_fixture(s3_client, python27_exec, postgres_engine, loop):
    pool = ThreadPoolExecutor(3)
    dsm_fixture = DataStorageManager(
        s3_client, python27_exec, postgres_engine, loop, pool, BUCKET_NAME)
    return dsm_fixture
