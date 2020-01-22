# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=unsupported-assignment-operation
# pylint:disable=no-name-in-module
# pylint:disable=no-member


import datetime
import os
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from random import randrange
from typing import Tuple

import pytest
from aiopg.sa import create_engine

import simcore_service_storage
import utils
from simcore_service_storage.datcore_wrapper import DatcoreWrapper
from simcore_service_storage.dsm import DataStorageManager, DatCoreApiToken
from simcore_service_storage.models import FileMetaData
from simcore_service_storage.settings import SIMCORE_S3_STR
from utils import (ACCESS_KEY, BUCKET_NAME, DATABASE, PASS, SECRET_KEY, USER,
                   USER_ID)

current_dir = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent
sys.path.append(str(current_dir / 'helpers'))



@pytest.fixture(scope='session')
def here():
    return current_dir

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
        'port': docker_services.port_for('postgres', 5432),
        'minsize':1,
        'maxsize':4
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
        'secure' : 0
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
def dsm_mockup_complete_db(postgres_service_url, s3_client) -> Tuple[str, str]:
    utils.create_full_tables(url=postgres_service_url)
    bucket_name = BUCKET_NAME
    s3_client.create_bucket(bucket_name, delete_contents_if_exists=True)
    file_1 = {
        "project_id": "161b8782-b13e-5840-9ae2-e2250c231001",
        "node_id": "ad9bda7f-1dc5-5480-ab22-5fef4fc53eac",
        "filename": "outputController.dat"
        }
    f = utils.data_dir() /Path("outputController.dat")
    object_name = "{project_id}/{node_id}/{filename}".format(**file_1)
    s3_client.upload_file(bucket_name, object_name, f)

    file_2 = {
        "project_id": "161b8782-b13e-5840-9ae2-e2250c231001",
        "node_id": "a3941ea0-37c4-5c1d-a7b3-01b5fd8a80c8",
        "filename": "notebooks.zip"
        }
    f = utils.data_dir() /Path("notebooks.zip")
    object_name = "{project_id}/{node_id}/{filename}".format(**file_2)
    s3_client.upload_file(bucket_name, object_name, f)
    yield (file_1,file_2)
    utils.drop_all_tables(url=postgres_service_url)


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
        raw_file_path = file_uuid
        display_file_path = str(Path(project_name)/Path(node)/Path(file_name))
        created_at = str(datetime.datetime.now())
        file_size = 1234
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
             'user_name': user_name,
             "file_id": str(uuid.uuid4()),
             "raw_file_path": file_uuid,
             "display_file_path": display_file_path,
             "created_at": created_at,
             "last_modified": created_at,
             "file_size": file_size,
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
async def datcore_testbucket(loop, mock_files_factory):
    # TODO: what if I do not have an app to the the config from?
    api_token = os.environ.get("BF_API_KEY")
    api_secret = os.environ.get("BF_API_SECRET")

    if api_secret is None:
        yield "no_bucket"
        return

    pool = ThreadPoolExecutor(2)
    dcw = DatcoreWrapper(api_token, api_secret, loop, pool)

    await dcw.create_test_dataset(BUCKET_NAME)
    tmp_files = mock_files_factory(2)
    for f in tmp_files:
        await dcw.upload_file(BUCKET_NAME, os.path.normpath(f))

    yield BUCKET_NAME, tmp_files[0], tmp_files[1]

    await dcw.delete_test_dataset(BUCKET_NAME)


@pytest.fixture(scope="function")
def dsm_fixture(s3_client, postgres_engine, loop):
    pool = ThreadPoolExecutor(3)
    dsm_fixture = DataStorageManager(
        s3_client, postgres_engine, loop, pool, BUCKET_NAME, False)

    api_token = os.environ.get("BF_API_KEY", "none")
    api_secret = os.environ.get("BF_API_SECRET", "none")
    dsm_fixture.datcore_tokens[USER_ID] = DatCoreApiToken(api_token, api_secret)

    return dsm_fixture


@pytest.fixture(scope="function")
async def datcore_structured_testbucket(loop, mock_files_factory):
    api_token = os.environ.get("BF_API_KEY")
    api_secret = os.environ.get("BF_API_SECRET")

    if api_secret is None:
        yield "no_bucket"
        return

    pool = ThreadPoolExecutor(2)
    dcw = DatcoreWrapper(api_token, api_secret, loop, pool)

    dataset_id = await dcw.create_test_dataset(BUCKET_NAME)
    tmp_files = mock_files_factory(3)
    # first file to the root
    file_id1 = await dcw.upload_file_to_id(dataset_id, os.path.normpath(tmp_files[0]))
    # create first level folder
    collection_id1 = await dcw.create_collection(dataset_id, "level1")
    # upload second file
    file_id2 = await dcw.upload_file_to_id(collection_id1, os.path.normpath(tmp_files[1]))

    # create 3rd level folder
    collection_id2 = await dcw.create_collection(collection_id1, "level2")
    file_id3 = await dcw.upload_file_to_id(collection_id2, os.path.normpath(tmp_files[2]))

    yield { 'dataset_id' : dataset_id,
        'coll1_id' : collection_id1, 'coll2_id' : collection_id2,
        'file_id1' : file_id1, 'filename1' : tmp_files[0],
        'file_id2' : file_id2, 'filename2' : tmp_files[1],
        'file_id3' : file_id3, 'filename3' : tmp_files[2],
        'dcw' : dcw }

    await dcw.delete_test_dataset(BUCKET_NAME)
