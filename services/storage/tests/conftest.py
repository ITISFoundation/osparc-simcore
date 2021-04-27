# pylint: disable=no-member
# pylint: disable=no-name-in-module
# pylint: disable=redefined-outer-name
# pylint: disable=unsupported-assignment-operation
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import datetime
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from random import randrange
from typing import Callable, Dict, Iterator, Tuple

import dotenv
import pytest
import simcore_service_storage
from aiohttp import web
from aiopg.sa import create_engine
from servicelib.application import create_safe_application
from simcore_service_storage.constants import SIMCORE_S3_STR
from simcore_service_storage.dsm import DataStorageManager, DatCoreApiToken
from simcore_service_storage.models import FileMetaData
from simcore_service_storage.s3wrapper.s3_client import MinioClientWrapper
from tests.utils import DATA_DIR

import tests

pytest_plugins = [
    "pytest_simcore.cli_runner",
    "pytest_simcore.repository_paths",
    "tests.fixtures.data_models",
    "pytest_simcore.repository_paths",
]


@pytest.fixture(scope="session")
def project_slug_dir(osparc_simcore_root_dir) -> Path:
    """Path to project slug directory"""
    # uses pytest_simcore.environs.osparc_simcore_root_dir
    service_folder = osparc_simcore_root_dir / "services" / "storage"
    assert service_folder.exists()
    assert any(service_folder.glob("src/simcore_service_storage"))
    return service_folder


@pytest.fixture(scope="session")
def package_dir() -> Path:
    """Path to directory of current package.

    Notice that this might be under src (if installed as edit mode)
    OR in the installation folder (in CI mode)
    """
    dirpath = Path(simcore_service_storage.__file__).resolve().parent
    assert dirpath.exists()
    return dirpath


@pytest.fixture(scope="session")
def project_env_devel_dict(project_slug_dir: Path) -> Dict:
    """Returns a dict of environment variables in project_slug_dir/.env-devel
    Those are default environment consumed by application settings
    """
    env_devel_file = project_slug_dir / ".env-devel"
    assert env_devel_file.exists()
    environ = dotenv.dotenv_values(env_devel_file, verbose=True, interpolate=True)
    return environ


@pytest.fixture(scope="function")
def patch_env_devel_environment(project_env_devel_dict, monkeypatch) -> None:
    """Patches environment variable with project_slug_dir/.env-devel"""
    for key, value in project_env_devel_dict.items():
        monkeypatch.setenv(key, value)


@pytest.fixture(scope="session")
def docker_compose_file(
    project_tests_dir: Path, patch_env_devel_environment
) -> Iterator[str]:
    """Overrides pytest-docker fixture"""
    # docker-compose reads these environs
    assert os.environ["POSTGRES_DB"]
    assert os.environ["POSTGRES_USER"]
    assert os.environ["POSTGRES_PASSWORD"]
    assert os.environ["MINIO_ACCESS_KEY"]
    assert os.environ["MINIO_SECRET_KEY"]

    dc_path = project_tests_dir / "docker-compose.yml"
    assert dc_path.exists()

    yield str(dc_path)


# POSTGRES SERVICES FIXTURES---------------------


@pytest.fixture(scope="session")
def postgres_service(docker_services, docker_ip, project_env_devel_dict):
    """
    Returns postgres service attributes, when up and responsive
    """

    user = project_env_devel_dict["POSTGRES_DB"]
    password = project_env_devel_dict["POSTGRES_PASSWORD"]
    database = project_env_devel_dict["POSTGRES_DB"]
    host = docker_ip
    port = docker_services.port_for("postgres", 5432)
    url = f"postgresql://{user}:{password}@{host}:{port}/{database}"

    # Wait until service is responsive.
    docker_services.wait_until_responsive(
        check=lambda: tests.utils.is_postgres_responsive(url),
        timeout=30.0,
        pause=0.1,
    )

    return {
        "user": user,
        "password": password,
        "db": database,
        "database": database,
        "host": host,
        "port": port,
        "minsize": 1,
        "maxsize": 4,
        "url": url,
    }


@pytest.fixture(scope="function")
def postgres_service_url(postgres_service, docker_services, docker_ip):
    url = postgres_service["url"]

    tests.utils.create_tables(url)

    yield url

    tests.utils.drop_tables(url)


@pytest.fixture(scope="function")
async def postgres_engine(loop, postgres_service_url):
    pg_engine = await create_engine(postgres_service_url)

    yield pg_engine

    if pg_engine:
        pg_engine.close()
        await pg_engine.wait_closed()


## MINIO SERVICE FIXTURES ----------------------------------------------


@pytest.fixture(scope="session")
def minio_service(docker_services, docker_ip, project_env_devel_dict)-> Dict[str, Any]:

    # Build URL to service listening on random port.
    host = docker_ip
    port = docker_services.port_for("minio", 9000)
    url = "http://{host}:{port}/"

    # Wait until service is responsive.
    docker_services.wait_until_responsive(
        check=lambda: tests.utils.is_responsive(url, 403),
        timeout=30.0,
        pause=0.1,
    )

    return {
        "url": url,
        "endpoint": f"{host}:{port}",
        "access_key": project_env_devel_dict["S3_ACCESS_KEY"],
        "secret_key": project_env_devel_dict["S3_SECRET_KEY"],
        "bucket_name": project_env_devel_dict["S3_BUCKET_NAME"],
        "secure": 0,
    }


@pytest.fixture(scope="module")
def s3_client(minio_service: Dict[str, Any]) -> MinioClientWrapper:

    s3_client = MinioClientWrapper(
        endpoint=minio_service["endpoint"],
        access_key=minio_service["access_key"],
        secret_key=minio_service["secret_key"],
    )
    return s3_client


## FAKE DATA FIXTURES ----------------------------------------------


@pytest.fixture(scope="function")
def mock_files_factory(tmpdir_factory) -> Callable:
    def _create_files(count):
        filepaths = []
        for _i in range(count):
            name = str(uuid.uuid4())
            filepath = os.path.normpath(
                str(tmpdir_factory.mktemp("data").join(name + ".txt"))
            )
            with open(filepath, "w") as fout:
                fout.write("Hello world\n")
            filepaths.append(filepath)

        return filepaths

    return _create_files


@pytest.fixture(scope="function")
def fake_file(mock_files_factory: Callable) -> Path:
    """ Creates fake file and returns path """
    file_path = mock_files_factory(count=1)[0]
    assert file_path.exits()
    return file_path


@pytest.fixture(scope="function")
def dsm_mockup_complete_db(
    postgres_service_url, s3_client, bucket_name: str
) -> Tuple[Dict[str, str], Dict[str, str]]:

    tests.utils.fill_tables_from_csv_files(url=postgres_service_url)

    file_1 = {
        "project_id": "161b8782-b13e-5840-9ae2-e2250c231001",
        "node_id": "ad9bda7f-1dc5-5480-ab22-5fef4fc53eac",
        "filename": "outputController.dat",
    }
    f = DATA_DIR / "outputController.dat"
    object_name = "{project_id}/{node_id}/{filename}".format(**file_1)
    s3_client.upload_file(bucket_name, object_name, f)

    file_2 = {
        "project_id": "161b8782-b13e-5840-9ae2-e2250c231001",
        "node_id": "a3941ea0-37c4-5c1d-a7b3-01b5fd8a80c8",
        "filename": "notebooks.zip",
    }
    f = DATA_DIR / "notebooks.zip"
    object_name = "{project_id}/{node_id}/{filename}".format(**file_2)
    s3_client.upload_file(bucket_name, object_name, f)
    return (file_1, file_2)


@pytest.fixture(scope="function")
def dsm_mockup_db(
    postgres_service_url, s3_client, mock_files_factory, bucket_name: str
) -> Iterator[Dict[str, FileMetaData]]:

    # TODO: use pip install Faker
    users = ["alice", "bob", "chuck", "dennis"]

    projects = [
        "astronomy",
        "biology",
        "chemistry",
        "dermatology",
        "economics",
        "futurology",
        "geology",
    ]
    location = SIMCORE_S3_STR

    nodes = ["alpha", "beta", "gamma", "delta"]

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
        object_name = Path(str(project_id), str(node_id), str(counter)).as_posix()
        file_uuid = Path(object_name).as_posix()
        raw_file_path = file_uuid
        display_file_path = str(Path(project_name) / Path(node) / Path(file_name))
        created_at = str(datetime.datetime.now())
        file_size = 1234
        assert s3_client.upload_file(bucket_name, object_name, _file)

        d = {
            "file_uuid": file_uuid,
            "location_id": "0",
            "location": location,
            "bucket_name": bucket_name,
            "object_name": object_name,
            "project_id": str(project_id),
            "project_name": project_name,
            "node_id": str(node_id),
            "node_name": node,
            "file_name": file_name,
            "user_id": str(user_id),
            "user_name": user_name,
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
        tests.utils.insert_metadata(postgres_service_url, data[object_name])

    total_count = 0
    for _obj in s3_client.list_objects(bucket_name, recursive=True):
        total_count = total_count + 1

    assert total_count == N

    yield data

    # s3 client
    s3_client.remove_bucket(bucket_name, delete_contents=True)


@pytest.fixture(scope="function")
async def datcore_testbucket(loop, mock_files_factory, bucket_name: str):
    # TODO: what if I do not have an app to the the config from?
    api_token = os.environ.get("BF_API_KEY")
    api_secret = os.environ.get("BF_API_SECRET")

    if api_secret is None:
        yield "no_bucket"
        return

    with ThreadPoolExecutor(2) as pool:
        dcw = DatcoreWrapper(api_token, api_secret, loop, pool)

        await dcw.create_test_dataset(bucket_name)
        tmp_files = mock_files_factory(2)
        for f in tmp_files:
            await dcw.upload_file(bucket_name, os.path.normpath(f))

        yield bucket_name, tmp_files[0], tmp_files[1]

        await dcw.delete_test_dataset(bucket_name)


@pytest.fixture(scope="function")
def moduleless_app(loop, aiohttp_server) -> web.Application:
    app: web.Application = create_safe_application()
    # creates a dummy server
    server = loop.run_until_complete(aiohttp_server(app))
    # server is destroyed on exit https://docs.aiohttp.org/en/stable/testing.html#pytest_aiohttp.aiohttp_server
    return app


@pytest.fixture(scope="function")
def dsm_fixture(
    s3_client, postgres_engine, loop, moduleless_app, bucket_name: str, user_id: int
):
    with ThreadPoolExecutor(3) as pool:
        dsm_fixture = DataStorageManager(
            s3_client=s3_client,
            engine=postgres_engine,
            loop=loop,
            pool=pool,
            simcore_bucket_name=bucket_name,
            has_project_db=False,
            app=moduleless_app,
        )

        api_token = os.environ.get("BF_API_KEY", "none")
        api_secret = os.environ.get("BF_API_SECRET", "none")
        dsm_fixture.datcore_tokens[user_id] = DatCoreApiToken(api_token, api_secret)

        yield dsm_fixture


@pytest.fixture(scope="function")
async def datcore_structured_testbucket(loop, mock_files_factory, bucket_name: str):
    api_token = os.environ.get("BF_API_KEY")
    api_secret = os.environ.get("BF_API_SECRET")

    if api_token is None or api_secret is None:
        yield "no_bucket"
        return

    with ThreadPoolExecutor(2) as pool:
        dcw = DatcoreWrapper(api_token, api_secret, loop, pool)

        dataset_id = await dcw.create_test_dataset(bucket_name)
        assert dataset_id, f"Could not create dataset {bucket_name}"

        tmp_files = mock_files_factory(3)

        # first file to the root
        filename1 = os.path.normpath(tmp_files[0])
        file_id1 = await dcw.upload_file_to_id(dataset_id, filename1)
        assert file_id1, f"Could not upload {filename1} to the root of {bucket_name}"

        # create first level folder
        collection_id1 = await dcw.create_collection(dataset_id, "level1")

        # upload second file
        filename2 = os.path.normpath(tmp_files[1])
        file_id2 = await dcw.upload_file_to_id(collection_id1, filename2)
        assert file_id2, f"Could not upload {filename2} to the {bucket_name}/level1"

        # create 3rd level folder
        filename3 = os.path.normpath(tmp_files[2])
        collection_id2 = await dcw.create_collection(collection_id1, "level2")
        file_id3 = await dcw.upload_file_to_id(collection_id2, filename3)
        assert file_id3, f"Could not upload {filename3} to the {bucket_name}/level1/level2"

        yield {
            "dataset_id": dataset_id,
            "coll1_id": collection_id1,
            "coll2_id": collection_id2,
            "file_id1": file_id1,
            "filename1": tmp_files[0],
            "file_id2": file_id2,
            "filename2": tmp_files[1],
            "file_id3": file_id3,
            "filename3": tmp_files[2],
            "dcw": dcw,
        }

        await dcw.delete_test_dataset(bucket_name)
