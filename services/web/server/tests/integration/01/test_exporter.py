# pylint:disable=redefined-outer-name,unused-argument,too-many-arguments
import asyncio
import cgi
import itertools
import json
import logging
import operator
import sys
import tempfile
from collections import deque
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from typing import (
    Any,
    AsyncIterator,
    Awaitable,
    Callable,
    Dict,
    Iterable,
    Iterator,
    List,
    Set,
    Tuple,
)
from unittest import mock

import aiofiles
import aiohttp.web
import aiopg
import aiopg.sa
import aioredis
import pytest
from aiohttp.test_utils import TestClient
from models_library.settings.redis import RedisConfig
from pytest_simcore.docker_registry import _pull_push_service
from pytest_simcore.helpers.utils_login import log_client_in
from servicelib.aiohttp.application import create_safe_application
from simcore_postgres_database.models.services import (
    services_access_rights,
    services_meta_data,
)
from simcore_service_webserver.application import (
    setup_director,
    setup_director_v2,
    setup_exporter,
    setup_login,
    setup_products,
    setup_projects,
    setup_resource_manager,
    setup_rest,
    setup_security,
    setup_session,
    setup_socketio,
    setup_storage,
    setup_users,
)
from simcore_service_webserver.catalog import setup_catalog
from simcore_service_webserver.constants import X_PRODUCT_NAME_HEADER
from simcore_service_webserver.db import setup_db
from simcore_service_webserver.db_models import projects
from simcore_service_webserver.exporter.async_hashing import Algorithm, checksum
from simcore_service_webserver.exporter.file_downloader import ParallelDownloader
from simcore_service_webserver.scicrunch.submodule_setup import (
    setup_scicrunch_submodule,
)
from simcore_service_webserver.security_roles import UserRole
from simcore_service_webserver.storage_handlers import get_file_download_url
from sqlalchemy.dialects.postgresql import insert as pg_insert
from yarl import URL

log = logging.getLogger(__name__)

pytest_simcore_core_services_selection = [
    "catalog",
    "dask-scheduler",
    "director-v2",
    "director",
    "migration",
    "postgres",
    "rabbit",
    "redis",
    "storage",
]
pytest_simcore_ops_services_selection = ["minio"]

CURRENT_DIR = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent

DATA_DIR = CURRENT_DIR.parent.parent / "data"
assert DATA_DIR.exists(), "expected folder under tests/data"

API_VERSION = "v0"
API_PREFIX = "/" + API_VERSION

# store only lowercase "v1", "v2", etc...
SUPPORTED_EXPORTER_VERSIONS = {"v1", "v2"}

REMAPPING_KEY = "__reverse__remapping__dict__key__"
KEYS_TO_IGNORE_FROM_COMPARISON = {
    "id",
    "uuid",
    "name",
    "creation_date",
    "last_change_date",
    "runHash",  # this changes after import, but the runnable states should remain the same
    "eTag",  # this must change
    REMAPPING_KEY,
}


@pytest.fixture(autouse=True)
def __drop_and_recreate_postgres__(
    database_from_template_before_each_function,
) -> Iterator[None]:
    yield


@pytest.fixture(autouse=True)
async def __delete_all_redis_keys__(redis_service: RedisConfig):
    client = await aioredis.create_redis_pool(redis_service.dsn, encoding="utf-8")
    await client.flushall()
    client.close()
    await client.wait_closed()

    yield
    # do nothing on teadown


@pytest.fixture
def client(
    loop: asyncio.AbstractEventLoop,
    aiohttp_client: Callable,
    app_config: Dict,
    postgres_with_template_db: aiopg.sa.engine.Engine,
    mock_orphaned_services: mock.Mock,
):
    cfg = deepcopy(app_config)

    assert cfg["rest"]["version"] == API_VERSION
    assert cfg["rest"]["enabled"]
    cfg["projects"]["enabled"] = True
    cfg["director"]["enabled"] = True

    # fake config
    app = create_safe_application(cfg)

    # activates only security+restAPI sub-modules
    setup_db(app)
    setup_session(app)
    setup_security(app)
    setup_rest(app)
    setup_login(app)
    setup_users(app)
    setup_socketio(app)
    setup_projects(app)
    setup_director(app)
    setup_director_v2(app)
    setup_exporter(app)
    setup_storage(app)
    setup_products(app)
    setup_catalog(app)
    setup_scicrunch_submodule(app)
    assert setup_resource_manager(app)

    yield loop.run_until_complete(
        aiohttp_client(
            app,
            server_kwargs={"port": cfg["main"]["port"], "host": cfg["main"]["host"]},
        )
    )


################ utils


async def login_user(client):
    """returns a logged in regular user"""
    return await log_client_in(client=client, user_data={"role": UserRole.USER.name})


def get_exported_projects() -> List[Path]:
    # These files are generated from the front-end
    # when the formatter be finished
    exporter_dir = DATA_DIR / "exporter"
    assert exporter_dir.exists()
    exported_files = [x for x in exporter_dir.glob("*.osparc")]
    assert exported_files, "expected *.osparc files, none found"
    return exported_files


@pytest.fixture
async def apply_access_rights(
    aiopg_engine: aiopg.sa.Engine,
) -> AsyncIterator[Callable[..., Awaitable[None]]]:
    async def grant_rights_to_services(services: List[Tuple[str, str]]) -> None:
        for service_key, service_version in services:
            metada_data_values = dict(
                key=service_key,
                version=service_version,
                owner=1,  # a user is required in the database for ownership of metadata
                name="",
                description=f"OVERRIDEN BY TEST in {__file__}",
            )

            access_rights_values = dict(
                key=service_key,
                version=service_version,
                gid=1,
                execute_access=True,
                write_access=True,
            )

            async with aiopg_engine.acquire() as conn:
                # pylint: disable=no-value-for-parameter
                await conn.execute(
                    pg_insert(services_meta_data)
                    .values(**metada_data_values)
                    .on_conflict_do_update(
                        index_elements=[
                            services_meta_data.c.key,
                            services_meta_data.c.version,
                        ],
                        set_=metada_data_values,
                    )
                )
                await conn.execute(
                    pg_insert(services_access_rights)
                    .values(**access_rights_values)
                    .on_conflict_do_update(
                        index_elements=[
                            services_access_rights.c.key,
                            services_access_rights.c.version,
                            services_access_rights.c.gid,
                            services_access_rights.c.product_name,
                        ],
                        set_=access_rights_values,
                    )
                )

    yield grant_rights_to_services


@pytest.fixture
async def grant_access_rights(
    apply_access_rights: Callable[..., Awaitable[None]]
) -> None:
    # services which require access
    services = [
        ("simcore/services/comp/itis/sleeper", "2.0.2"),
        ("simcore/services/comp/itis/sleeper", "2.1.1"),
    ]
    await apply_access_rights(services)


@pytest.fixture(scope="session")
def push_services_to_registry(docker_registry: str, node_meta_schema: Dict) -> None:
    """Adds a itisfoundation/sleeper in docker registry"""
    # Used by V1 study
    _pull_push_service(
        "itisfoundation/sleeper", "2.0.2", docker_registry, node_meta_schema
    )
    # Used by V2 study (mainly for the addition of units)
    _pull_push_service(
        "itisfoundation/sleeper", "2.1.1", docker_registry, node_meta_schema
    )


@contextmanager
def assemble_tmp_file_path(file_name: str) -> Iterable[Path]:
    # pylint: disable=protected-access
    # let us all thank codeclimate for this beautiful piece of code
    tmp_store_dir = Path("/") / f"tmp/{next(tempfile._get_candidate_names())}"
    tmp_store_dir.mkdir(parents=True, exist_ok=True)
    file_path = tmp_store_dir / file_name

    try:
        yield file_path
    finally:
        file_path.unlink()
        tmp_store_dir.rmdir()


async def query_project_from_db(
    aiopg_engine: aiopg.sa.Engine, project_uuid: str
) -> Dict[str, Any]:
    async with aiopg_engine.acquire() as conn:
        project_result = await conn.execute(
            projects.select().where(projects.c.uuid == project_uuid)
        )
        project = await project_result.first()
        assert project is not None
        return dict(project)


def replace_uuids_with_sequences(original_project: Dict[str, Any]) -> Dict[str, Any]:
    # first make a copy
    project = deepcopy(original_project)
    workbench = project["workbench"]
    ui = project["ui"]

    # extract keys in correct order based on node names to have an accurate comparison
    node_uuid_service_label_dict = {key: workbench[key]["label"] for key in workbench}
    # sort by node label name and store node key
    sorted_node_uuid_service_label_dict = [
        k
        for k, v in sorted(
            node_uuid_service_label_dict.items(), key=lambda item: item[1]
        )
    ]
    # map node key to a sequential value
    remapping_dict = {
        key: f"uuid_seq_{i}"
        for i, key in enumerate(sorted_node_uuid_service_label_dict + [project["uuid"]])
    }

    str_workbench = json.dumps(workbench)
    str_ui = json.dumps(ui)
    for search_key, replace_key in remapping_dict.items():
        str_workbench = str_workbench.replace(search_key, replace_key)
        str_ui = str_ui.replace(search_key, replace_key)

    project["workbench"] = json.loads(str_workbench)
    project["ui"] = json.loads(str_ui)
    # store for later usage
    project[REMAPPING_KEY] = remapping_dict

    return project


def dict_with_keys(dict_data: Dict[str, Any], kept_keys: Set[str]) -> Dict[str, Any]:
    modified_dict = {}
    for key, value in dict_data.items():
        if key in kept_keys:
            # keep the whole object
            modified_dict[key] = deepcopy(value)
        # if it's a nested dict go deeper
        elif isinstance(value, dict):
            possible_nested_dict = dict_with_keys(value, kept_keys)
            if possible_nested_dict:
                modified_dict[key] = possible_nested_dict

    return modified_dict


def dict_without_keys(
    dict_data: Dict[str, Any], skipped_keys: Set[str]
) -> Dict[str, Any]:

    modified_dict = {}
    for key, value in dict_data.items():
        if key not in skipped_keys:
            if isinstance(value, dict):
                modified_dict[key] = dict_without_keys(value, skipped_keys)
            else:
                modified_dict[key] = deepcopy(value)
    return modified_dict


def assert_combined_entires_condition(
    *entries: Any, condition_operator: Callable
) -> None:
    """Ensures the condition_operator is True for all unique combinations"""
    for combination in itertools.combinations(entries, 2):
        assert condition_operator(combination[0], combination[1]) is True


def extract_original_files_for_node_sequence(
    project: Dict[str, Any], normalized_project: Dict[str, Any]
) -> Dict[str, Dict[str, str]]:
    """
    Extracts path and store from ouput_1 field of each node and
    returns mapped to the normalized data node keys for simpler comparison
    """
    results = {}
    reverse_search_dict = normalized_project[REMAPPING_KEY]

    for uuid_key, node in project["workbench"].items():
        output_1 = node["outputs"]["output_1"]
        sequence_key = reverse_search_dict[uuid_key]
        results[sequence_key] = {"store": output_1["store"], "path": output_1["path"]}

    return results


async def extract_download_links_from_storage(
    app: aiohttp.web.Application,
    original_files: Dict[str, Dict[str, str]],
    user_id: str,
) -> Dict[str, str]:
    async def _get_mapped_link(
        seq_key: str, location_id: str, raw_file_path: str
    ) -> Tuple[str, str]:
        link = await get_file_download_url(
            app=app,
            location_id=location_id,
            fileId=raw_file_path,
            user_id=int(user_id),
        )
        return seq_key, link

    tasks = deque()
    for seq_key, data in original_files.items():
        tasks.append(
            _get_mapped_link(
                seq_key=seq_key,
                location_id=data["store"],
                raw_file_path=data["path"],
            )
        )

    results = await asyncio.gather(*tasks)

    return {x[0]: x[1] for x in results}


async def download_files_and_get_checksums(
    app: aiohttp.web.Application, download_links: Dict[str, str]
) -> Dict[str, str]:
    with tempfile.TemporaryDirectory() as store_dir:
        download_paths = {}
        parallel_downloader = ParallelDownloader()
        for seq_id, url in download_links.items():
            download_path = Path(store_dir) / seq_id
            await parallel_downloader.append_file(link=url, download_path=download_path)
            download_paths[seq_id] = download_path

        await parallel_downloader.download_files(app=app)

        # compute checksums for each downloaded file
        checksums = {}
        for seq_id, download_path in download_paths.items():
            checksums[seq_id] = await checksum(
                file_path=download_path, algorithm=Algorithm.SHA256
            )

        return checksums


async def get_checksums_for_files_in_storage(
    app: aiohttp.web.Application,
    project: Dict[str, Any],
    normalized_project: Dict[str, Any],
    user_id: str,
) -> Dict[str, str]:
    original_files = extract_original_files_for_node_sequence(
        project=project, normalized_project=normalized_project
    )

    download_links = await extract_download_links_from_storage(
        app=app, original_files=original_files, user_id=user_id
    )

    files_checksums = await download_files_and_get_checksums(
        app=app,
        download_links=download_links,
    )

    return files_checksums


################ end utils


async def import_study_from_file(client, file_path: Path) -> str:
    url_import = client.app.router["import_project"].url_for()
    assert url_import == URL(API_PREFIX + "/projects:import")

    data = {"fileName": open(file_path, mode="rb")}
    async with await client.post(url_import, data=data, timeout=10) as import_response:
        assert import_response.status == 200, await import_response.text()
        reply_data = await import_response.json()
        assert reply_data.get("data") is not None

    imported_project_uuid = reply_data["data"]["uuid"]
    return imported_project_uuid


@pytest.mark.parametrize(
    "export_version", get_exported_projects(), ids=(lambda p: p.name)
)
async def test_import_export_import_duplicate(
    client: TestClient,
    push_services_to_registry: None,
    aiopg_engine: aiopg.sa.engine.Engine,
    redis_client: aioredis.Redis,
    export_version: Path,
    simcore_services_ready: None,
    grant_access_rights: None,
):
    """
    Checks if the full "import -> export -> import -> duplicate" cycle
    produces the same result in the DB.
    """

    user = await login_user(client)
    export_file_name = export_version.name
    version_from_name = export_file_name.split("#")[0]

    assert_error = (
        f"The '{version_from_name}' version' is not present in the supported versions: "
        f"{SUPPORTED_EXPORTER_VERSIONS}. If it's a new version please remember to add it."
    )
    assert version_from_name in SUPPORTED_EXPORTER_VERSIONS, assert_error

    imported_project_uuid = await import_study_from_file(client, export_version)

    headers = {X_PRODUCT_NAME_HEADER: "osparc"}

    # export newly imported project
    url_export = client.app.router["export_project"].url_for(
        project_id=imported_project_uuid
    )

    assert url_export == URL(API_PREFIX + f"/projects/{imported_project_uuid}:xport")
    async with await client.post(
        f"{url_export}", headers=headers, timeout=10
    ) as export_response:
        assert export_response.status == 200, await export_response.text()

        content_disposition_header = export_response.headers["Content-Disposition"]
        file_to_download_name = cgi.parse_header(content_disposition_header)[1][
            "filename"
        ]
        assert file_to_download_name.endswith(".osparc")

        with assemble_tmp_file_path(file_to_download_name) as downloaded_file_path:
            async with aiofiles.open(downloaded_file_path, mode="wb") as f:
                await f.write(await export_response.read())
                log.info("output_path %s", downloaded_file_path)

            reimported_project_uuid = await import_study_from_file(
                client, downloaded_file_path
            )

    # duplicate newly imported project
    url_duplicate = client.app.router["duplicate_project"].url_for(
        project_id=imported_project_uuid
    )
    assert url_duplicate == URL(
        API_PREFIX + f"/projects/{imported_project_uuid}:duplicate"
    )
    async with await client.post(
        f"{url_duplicate}", headers=headers, timeout=10
    ) as duplicate_response:
        assert duplicate_response.status == 200, await duplicate_response.text()
        reply_data = await duplicate_response.json()
        assert reply_data.get("data") is not None

        duplicated_project_uuid = reply_data["data"]["uuid"]

    imported_project = await query_project_from_db(aiopg_engine, imported_project_uuid)
    reimported_project = await query_project_from_db(
        aiopg_engine, reimported_project_uuid
    )
    duplicated_project = await query_project_from_db(
        aiopg_engine, duplicated_project_uuid
    )

    # uuids are changed each time the project is imported, need to normalize them
    normalized_imported_project = replace_uuids_with_sequences(imported_project)
    normalized_reimported_project = replace_uuids_with_sequences(reimported_project)
    normalized_duplicated_project = replace_uuids_with_sequences(duplicated_project)

    # ensure values are different
    assert_combined_entires_condition(
        dict_with_keys(normalized_imported_project, KEYS_TO_IGNORE_FROM_COMPARISON),
        dict_with_keys(normalized_reimported_project, KEYS_TO_IGNORE_FROM_COMPARISON),
        dict_with_keys(normalized_duplicated_project, KEYS_TO_IGNORE_FROM_COMPARISON),
        condition_operator=operator.ne,
    )

    # assert same structure in both directories
    assert_combined_entires_condition(
        dict_without_keys(normalized_imported_project, KEYS_TO_IGNORE_FROM_COMPARISON),
        dict_without_keys(
            normalized_reimported_project, KEYS_TO_IGNORE_FROM_COMPARISON
        ),
        dict_without_keys(
            normalized_duplicated_project, KEYS_TO_IGNORE_FROM_COMPARISON
        ),
        condition_operator=operator.eq,
    )

    # check files in storage fingerprint matches
    imported_files_checksums = await get_checksums_for_files_in_storage(
        app=client.app,
        project=imported_project,
        normalized_project=normalized_imported_project,
        user_id=user["id"],
    )
    reimported_files_checksums = await get_checksums_for_files_in_storage(
        app=client.app,
        project=reimported_project,
        normalized_project=normalized_reimported_project,
        user_id=user["id"],
    )
    duplicated_files_checksums = await get_checksums_for_files_in_storage(
        app=client.app,
        project=duplicated_project,
        normalized_project=normalized_duplicated_project,
        user_id=user["id"],
    )

    assert_combined_entires_condition(
        imported_files_checksums,
        reimported_files_checksums,
        duplicated_files_checksums,
        condition_operator=operator.eq,
    )
