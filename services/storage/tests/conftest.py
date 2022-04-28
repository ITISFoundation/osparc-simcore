# pylint: disable=no-member
# pylint: disable=no-name-in-module
# pylint: disable=redefined-outer-name
# pylint: disable=unsupported-assignment-operation
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import datetime
import os
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from random import randrange
from typing import Any, Callable, Dict, Iterable, Iterator, List

import dotenv
import pytest
import simcore_service_storage
from aiohttp import web
from aiopg.sa import Engine
from servicelib.aiohttp.application import create_safe_application
from simcore_service_storage.constants import SIMCORE_S3_STR
from simcore_service_storage.dsm import DataStorageManager, DatCoreApiToken
from simcore_service_storage.models import FileMetaData, file_meta_data, projects, users
from simcore_service_storage.s3wrapper.s3_client import MinioClientWrapper
from tests.utils import BUCKET_NAME, DATA_DIR, USER_ID

import tests

pytest_plugins = [
    "pytest_simcore.cli_runner",
    "pytest_simcore.repository_paths",
    "tests.fixtures.data_models",
    "pytest_simcore.pytest_global_environs",
]

CURRENT_DIR = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent

# TODO: replace by pytest_simcore
sys.path.append(str(CURRENT_DIR / "helpers"))


@pytest.fixture(scope="session")
def here() -> Path:
    return CURRENT_DIR


@pytest.fixture(scope="session")
def package_dir(here) -> Path:
    dirpath = Path(simcore_service_storage.__file__).parent
    assert dirpath.exists()
    return dirpath


@pytest.fixture(scope="session")
def osparc_simcore_root_dir(here) -> Path:
    root_dir = here.parent.parent.parent
    assert root_dir.exists() and any(
        root_dir.glob("services")
    ), "Is this service within osparc-simcore repo?"
    return root_dir


@pytest.fixture(scope="session")
def osparc_api_specs_dir(osparc_simcore_root_dir) -> Path:
    dirpath = osparc_simcore_root_dir / "api" / "specs"
    assert dirpath.exists()
    return dirpath


@pytest.fixture(scope="session")
def project_slug_dir(osparc_simcore_root_dir) -> Path:
    # uses pytest_simcore.environs.osparc_simcore_root_dir
    service_folder = osparc_simcore_root_dir / "services" / "storage"
    assert service_folder.exists()
    assert any(service_folder.glob("src/simcore_service_storage"))
    return service_folder


@pytest.fixture(scope="session")
def project_env_devel_dict(project_slug_dir: Path) -> Dict:
    env_devel_file = project_slug_dir / ".env-devel"
    assert env_devel_file.exists()
    environ = dotenv.dotenv_values(env_devel_file, verbose=True, interpolate=True)
    return environ


@pytest.fixture(scope="function")
def project_env_devel_environment(project_env_devel_dict, monkeypatch) -> None:
    for key, value in project_env_devel_dict.items():
        monkeypatch.setenv(key, value)


@pytest.fixture(scope="module")
def s3_client(minio_config: Dict[str, Any]) -> MinioClientWrapper:

    s3_client = MinioClientWrapper(
        endpoint=minio_config["client"]["endpoint"],
        access_key=minio_config["client"]["access_key"],
        secret_key=minio_config["client"]["secret_key"],
    )
    return s3_client


## FAKE DATA FIXTURES ----------------------------------------------


@pytest.fixture(scope="function")
def mock_files_factory(tmpdir_factory) -> Callable[[int], List[Path]]:
    def _create_files(count: int) -> List[Path]:
        filepaths = []
        for _i in range(count):
            filepath = Path(tmpdir_factory.mktemp("data")) / f"{uuid.uuid4()}.txt"
            filepath.write_text("Hello world\n")
            filepaths.append(filepath)

        return filepaths

    return _create_files


@pytest.fixture
async def cleanup_user_projects_file_metadata(aiopg_engine: Engine):
    yield
    # cleanup
    async with aiopg_engine.acquire() as conn:
        await conn.execute(file_meta_data.delete())
        await conn.execute(projects.delete())
        await conn.execute(users.delete())


@pytest.fixture
def dsm_mockup_complete_db(
    postgres_dsn, s3_client, cleanup_user_projects_file_metadata
) -> Iterator[tuple[dict[str, str], dict[str, str]]]:
    dsn = "postgresql://{user}:{password}@{host}:{port}/{database}".format(
        **postgres_dsn
    )
    tests.utils.fill_tables_from_csv_files(url=dsn)

    bucket_name = BUCKET_NAME
    s3_client.create_bucket(bucket_name, delete_contents_if_exists=True)
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
    yield (file_1, file_2)

    # cleanup
    s3_client.remove_bucket(bucket_name, delete_contents=True)


@pytest.fixture
def dsm_mockup_db(
    postgres_dsn_url,
    s3_client: MinioClientWrapper,
    mock_files_factory: Callable[[int], List[Path]],
    cleanup_user_projects_file_metadata,
) -> Iterator[dict[str, FileMetaData]]:

    # s3 client
    bucket_name = BUCKET_NAME
    s3_client.create_bucket(bucket_name, delete_contents_if_exists=True)

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
    files = mock_files_factory(N)
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
        created_at = str(datetime.datetime.utcnow())
        file_size = _file.stat().st_size

        assert s3_client.upload_file(bucket_name, object_name, _file)
        s3_meta_data = s3_client.get_metadata(bucket_name, object_name)
        assert "ETag" in s3_meta_data
        entity_tag = s3_meta_data["ETag"].strip('"')

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
            "entity_tag": entity_tag,
        }

        counter = counter + 1

        data[object_name] = FileMetaData(**d)

        # pylint: disable=no-member

        tests.utils.insert_metadata(postgres_dsn_url, data[object_name])

    total_count = 0
    for _obj in s3_client.list_objects(bucket_name, recursive=True):
        total_count = total_count + 1

    assert total_count == N

    yield data

    # s3 client
    s3_client.remove_bucket(bucket_name, delete_contents=True)


@pytest.fixture(scope="function")
def moduleless_app(event_loop, aiohttp_server) -> web.Application:
    app: web.Application = create_safe_application()
    # creates a dummy server
    server = event_loop.run_until_complete(aiohttp_server(app))
    # server is destroyed on exit https://docs.aiohttp.org/en/stable/testing.html#pytest_aiohttp.aiohttp_server
    return app


@pytest.fixture(scope="function")
def dsm_fixture(
    s3_client, aiopg_engine, event_loop, moduleless_app
) -> Iterable[DataStorageManager]:

    with ThreadPoolExecutor(3) as pool:
        dsm_fixture = DataStorageManager(
            s3_client=s3_client,
            engine=aiopg_engine,
            loop=event_loop,
            pool=pool,
            simcore_bucket_name=BUCKET_NAME,
            has_project_db=False,
            app=moduleless_app,
        )

        api_token = os.environ.get("BF_API_KEY", "none")
        api_secret = os.environ.get("BF_API_SECRET", "none")
        dsm_fixture.datcore_tokens[USER_ID] = DatCoreApiToken(api_token, api_secret)

        yield dsm_fixture


@pytest.fixture(scope="function")
async def datcore_structured_testbucket(
    mock_files_factory: Callable[[int], List[Path]],
    moduleless_app,
):
    api_token = os.environ.get("BF_API_KEY")
    api_secret = os.environ.get("BF_API_SECRET")

    if api_token is None or api_secret is None:
        yield "no_bucket"
        return
    import warnings

    warnings.warn("DISABLED!!!")
    raise Exception
    # TODO: there are some missing commands in datcore-adapter before this can run
    # this shall be used when the time comes and this code should be enabled again

    # dataset: DatasetMetaData = await datcore_adapter.create_dataset(
    #     moduleless_app, api_token, api_secret, BUCKET_NAME
    # )
    # dataset_id = dataset.dataset_id
    # assert dataset_id, f"Could not create dataset {BUCKET_NAME}"

    # tmp_files = mock_files_factory(3)

    # # first file to the root
    # filename1 = os.path.normpath(tmp_files[0])
    # await datcore_adapter.upload_file(moduleless_app, api_token, api_secret, filename1)
    # file_id1 = await dcw.upload_file_to_id(dataset_id, filename1)
    # assert file_id1, f"Could not upload {filename1} to the root of {BUCKET_NAME}"

    # # create first level folder
    # collection_id1 = await dcw.create_collection(dataset_id, "level1")

    # # upload second file
    # filename2 = os.path.normpath(tmp_files[1])
    # file_id2 = await dcw.upload_file_to_id(collection_id1, filename2)
    # assert file_id2, f"Could not upload {filename2} to the {BUCKET_NAME}/level1"

    # # create 3rd level folder
    # filename3 = os.path.normpath(tmp_files[2])
    # collection_id2 = await dcw.create_collection(collection_id1, "level2")
    # file_id3 = await dcw.upload_file_to_id(collection_id2, filename3)
    # assert file_id3, f"Could not upload {filename3} to the {BUCKET_NAME}/level1/level2"

    # yield {
    #     "dataset_id": dataset_id,
    #     "coll1_id": collection_id1,
    #     "coll2_id": collection_id2,
    #     "file_id1": file_id1,
    #     "filename1": tmp_files[0],
    #     "file_id2": file_id2,
    #     "filename2": tmp_files[1],
    #     "file_id3": file_id3,
    #     "filename3": tmp_files[2],
    #     "dcw": dcw,
    # }

    # await dcw.delete_test_dataset(BUCKET_NAME)
