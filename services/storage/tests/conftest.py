# TODO: W0611:Unused import ...
# pylint: disable=W0611
# TODO: W0613:Unused argument ...
# pylint: disable=W0613
#
# pylint: disable=W0621
import os
import sys
import uuid
from collections import namedtuple
from pathlib import Path
from random import randrange

import pytest
import subprocess
import simcore_service_storage
import utils
from simcore_service_storage.models import FileMetaData
from utils import ACCESS_KEY, BUCKET_NAME, DATABASE, PASS, SECRET_KEY, USER

# fixtures -------------------------------------------------------

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
    assert root_dir.exists(), "Is this service within osparc-simcore repo?"
    return root_dir

@pytest.fixture(scope='session')
def python27_exec(osparc_simcore_root_dir, tmpdir_factory, here):
    # Assumes already created with make .venv27
    venv27 = osparc_simcore_root_dir / ".venv27"

    if not venv27.exists():
        # create its own virtualenv
        venv27 = tmpdir_factory.mktemp("virtualenv") / ".venv27"
        cmd = "virtualenv --python=python2 %s"%(venv27) # TODO: how to split in command safely?
        assert subprocess.check_call(cmd.split()) == 0, "Unable to run %s" %cmd

        # installs python2 requirements
        pip_exec = venv27 / "bin" / "pip"
        requirements_py2 = here.parent / "requirements/py27.txt"
        cmd = "{} install -r {}".format(pip_exec, requirements_py2)
        assert subprocess.check_call(cmd.split()) == 0, "Unable to run %s" %cmd


    python27_exec = venv27 / "bin" / "python2.7"
    assert python27_exec.exists()
    return python27_exec


@pytest.fixture(scope='session')
def docker_compose_file(here):
    """ Overrides pytest-docker fixture
    """
    old = os.environ.copy()

    # docker-compose reads these environs
    os.environ['POSTGRES_DB']=DATABASE
    os.environ['POSTGRES_USER']=USER
    os.environ['POSTGRES_PASSWORD']=PASS
    os.environ['POSTGRES_ENDPOINT']="FOO" # TODO: update config schema!!
    os.environ['MINIO_ACCESS_KEY']=ACCESS_KEY
    os.environ['MINIO_SECRET_KEY']=SECRET_KEY

    dc_path = here / 'docker-compose.yml'

    assert dc_path.exists()
    yield str(dc_path)

    os.environ = old

@pytest.fixture(scope='session')
def postgres_service(docker_services, docker_ip):
    url = 'postgresql://{user}:{password}@{host}:{port}/{database}'.format(
        user = USER,
        password = PASS,
        database = DATABASE,
        host=docker_ip,
        port=docker_services.port_for('postgres', 5432),
    )

    # Wait until service is responsive.
    docker_services.wait_until_responsive(
        check=lambda: utils.is_postgres_responsive(url),
        timeout=30.0,
        pause=0.1,
    )

    return url

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
        'secret_key' : SECRET_KEY,
        }

@pytest.fixture(scope="module")
def s3_client(minio_service):
    from s3wrapper.s3_client import S3Client

    s3_client = S3Client(**minio_service)
    return s3_client

@pytest.fixture(scope="function")
def mock_files_factory(tmpdir_factory):
    def _create_files(count):
        filepaths = []
        for _i in range(count):
            name = str(uuid.uuid4())
            filepath = os.path.normpath(str(tmpdir_factory.mktemp('data').join(name + ".txt")))
            with open(filepath, 'w') as fout:
                fout.write("Hello world\n")
            filepaths.append(filepath)

        return filepaths
    return _create_files


@pytest.fixture(scope="function")
def dsm_mockup_db(postgres_service, s3_client, mock_files_factory):
    # db
    utils.create_tables(url=postgres_service)

    # s3 client
    bucket_name = BUCKET_NAME
    s3_client.create_bucket(bucket_name, delete_contents_if_exists=True)

    #TODO: use pip install Faker
    users = [ 'alice', 'bob', 'chuck', 'dennis']

    projects = ['astronomy', 'biology', 'chemistry', 'dermatology', 'economics', 'futurology', 'geology']
    location = "simcore.s3"

    nodes = ['alpha', 'beta', 'gamma', 'delta']

    N = 100

    files = mock_files_factory(count=N)
    counter = 0
    data = {}
    for _file in files:
        idx = randrange(len(users))
        user = users[idx]
        user_id = idx + 10
        idx =  randrange(len(projects))
        project = projects[idx]
        project_id = idx + 100
        idx =  randrange(len(nodes))
        node = nodes[idx]
        node_id = idx + 10000
        file_id = str(uuid.uuid4())
        file_name = str(counter)
        counter = counter + 1
        object_name = os.path.join(str(project_id), str(node_id), str(counter))
        assert s3_client.upload_file(bucket_name, object_name, _file)


        d = { 'object_name' : object_name,
              'bucket_name' : bucket_name,
              'file_id' : file_id,
              'file_name' : file_name,
              'user_id' : user_id,
              'user_name' : user,
              'location' : location,
              'project_id' : project_id,
              'project_name' : project,
              'node_id' : node_id,
              'node_name' : node
             }

        data[object_name] = FileMetaData(**d)


        utils.insert_metadata(postgres_service, object_name, bucket_name, file_id, file_name, user_id,
            user, location, project_id, project, node_id, node)


    total_count = 0
    for _obj in s3_client.list_objects_v2(bucket_name, recursive = True):
        total_count = total_count + 1

    assert total_count == N
    yield data

    # s3 client
    s3_client.remove_bucket(bucket_name, delete_contents=True)

    # db
    utils.drop_tables(url=postgres_service)
