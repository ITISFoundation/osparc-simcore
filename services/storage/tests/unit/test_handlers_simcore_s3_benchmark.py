# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import datetime
import json
import sys
import time
from collections.abc import AsyncIterator, Iterable
from contextlib import AsyncExitStack, asynccontextmanager
from itertools import groupby
from pathlib import Path
from typing import Any, TypeAlias, TypedDict
from uuid import uuid4

import pytest
from faker import Faker
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID, SimcoreS3FileID
from pydantic import BaseModel, ByteSize, parse_file_as, parse_obj_as
from pytest_mock import MockerFixture
from servicelib.utils import logged_gather
from settings_library.s3 import S3Settings
from simcore_service_storage import s3_client
from simcore_service_storage.models import S3BucketName
from simcore_service_storage.s3_client import StorageS3Client
from simcore_service_storage.settings import Settings

CURRENT_DIR = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent


def _get_benchmark_s3_settings() -> list[S3Settings]:
    # NOTE: if this file is defined tests will be activated using said bucket
    path_to_file = CURRENT_DIR / "s3_settings_benchmark.ignore.json"
    if path_to_file.exists():
        return parse_file_as(list[S3Settings], path_to_file)

    return []


@pytest.fixture(params=_get_benchmark_s3_settings())
async def benchmark_s3_settings(request: pytest.FixtureRequest) -> S3Settings:
    return request.param


@pytest.fixture
def settings() -> Settings:
    return Settings.create_from_envs()


@pytest.fixture
async def benchmark_s3_client(
    benchmark_s3_settings: S3Settings, settings: Settings
) -> AsyncIterator[StorageS3Client]:
    async with AsyncExitStack() as exit_stack:
        client = await StorageS3Client.create(
            exit_stack,
            benchmark_s3_settings,
            settings.STORAGE_S3_CLIENT_MAX_TRANSFER_CONCURRENCY,
        )
        bucket = S3BucketName(benchmark_s3_settings.S3_BUCKET_NAME)

        # make sure bucket is empty
        await client.delete_files_in_path(bucket, prefix="")

        yield client

        # empty bucket once more when done testing
        await client.delete_files_in_path(bucket, prefix="")


@asynccontextmanager
async def temp_file(size: ByteSize) -> AsyncIterator[Path]:
    file_path = Path(f"/tmp/{uuid4()}")
    file_path.write_text("a" * size)
    assert file_path.exists() is True

    yield file_path

    file_path.unlink()
    assert file_path.exists() is False


async def _create_file(
    s3_client: StorageS3Client,
    bucket: S3BucketName,
    file_id: SimcoreS3FileID,
    size: ByteSize = parse_obj_as(ByteSize, "1"),
) -> None:
    async with temp_file(size) as file:
        await s3_client.upload_file(
            bucket=bucket, file=file, file_id=file_id, bytes_transfered_cb=None
        )


def _create_node_structure(
    root_node: str, level: int, dirs_per_node: int, files_per_node: int
) -> set[str]:
    if level == 0:
        return set()

    leaves: set[str] = set()
    for f in range(files_per_node):
        p = f"{root_node}/f{f}"
        leaves.add(p)

    for d in range(dirs_per_node):
        new_leaves = _create_node_structure(
            root_node + f"/l{level}/d{d}", level - 1, dirs_per_node, files_per_node
        )
        leaves.update(new_leaves)

    return leaves


async def _create_files(
    s3_client: StorageS3Client,
    bucket: S3BucketName,
    project_id: ProjectID,
    node_id: NodeID,
    *,
    depth: int,
    dirs_per_dir: int,
    files_per_dir: int,
) -> set[SimcoreS3FileID]:
    elements = _create_node_structure(
        root_node="",
        level=depth,
        dirs_per_node=dirs_per_dir,
        files_per_node=files_per_dir,
    )
    file_ids: set[SimcoreS3FileID] = {
        parse_obj_as(SimcoreS3FileID, f"{project_id}/{node_id}/{key}")
        for key in elements
    }

    await logged_gather(
        *[_create_file(s3_client, bucket, file_id) for file_id in file_ids],
        max_concurrency=20,
    )

    return file_ids


@pytest.fixture(scope="session")
def tests_session_id() -> str:
    return datetime.datetime.utcnow().isoformat()


class MetricsResult(BaseModel):
    session_id: str
    duration_ms: float
    tags: dict[str, str]


class MetricsResultList(BaseModel):
    __root__: list[MetricsResult]


_TEST_RESULTS: Path = CURRENT_DIR / "test_results.ignore.json"


@asynccontextmanager
async def metrics(tests_session_id: str, tags: dict[str, str]) -> AsyncIterator[None]:
    if not _TEST_RESULTS.exists():
        _TEST_RESULTS.write_text(json.dumps([]))

    start = time.time_ns()

    yield None

    elapsed_ms = (time.time_ns() - start) / 1e6

    metrics_results = parse_file_as(list[MetricsResult], _TEST_RESULTS)
    metrics_results.append(
        MetricsResult(session_id=tests_session_id, duration_ms=elapsed_ms, tags=tags)
    )
    _TEST_RESULTS.write_text(MetricsResultList.parse_obj(metrics_results).json())


@pytest.fixture
def mock_max_items(mocker: MockerFixture) -> None:
    # pylint: disable=protected-access
    mocker.patch.object(
        s3_client._list_objects_v2_paginated_gen, "__defaults__", (None,)
    )


@pytest.mark.parametrize("total_queries", [3])
@pytest.mark.parametrize(
    "depth, dirs_per_dir, files_per_dir, description",
    [
        (1, 10, 3, "very few files"),
        (1, 1, 1092, "1092 files in one dir"),
        (1, 1, 3279, "3279 files in one dir"),
        (6, 3, 3, "spread out files and dirs"),
        (7, 3, 3, "lots of spread files and dirs"),
    ],
)
async def test_benchmark_s3_listing(
    # pylint: disable=too-many-arguments
    mock_max_items: None,
    benchmark_s3_client: StorageS3Client,
    benchmark_s3_settings: S3Settings,
    faker: Faker,
    tests_session_id: str,
    depth: int,
    dirs_per_dir: int,
    files_per_dir: int,
    total_queries: int,
    description: str,
    generate_report: None,
):
    project_id = faker.uuid4(cast_to=None)
    node_id = faker.uuid4(cast_to=None)

    bucket: S3BucketName = S3BucketName(benchmark_s3_settings.S3_BUCKET_NAME)

    created_fils: set[SimcoreS3FileID] = await _create_files(
        benchmark_s3_client,
        bucket,
        project_id,
        node_id,
        depth=depth,
        dirs_per_dir=dirs_per_dir,
        files_per_dir=files_per_dir,
    )

    for i in range(total_queries):
        async with metrics(
            tests_session_id=tests_session_id,
            tags={
                "from": "Z43",
                "to": benchmark_s3_settings.S3_ENDPOINT,
                "query": "list_files(prefix='')",
                "total_queries": f"{total_queries}",
                "query_number": f"{i +1}",
                "reason": description,
                "depth": f"{depth}",
                "dirs_per_dir": f"{dirs_per_dir}",
                "files_per_dir": f"{files_per_dir}",
                "generated_file_count": f"{len(created_fils)}",
            },
        ):
            files = await benchmark_s3_client.list_files(bucket, prefix="")
        assert len(files) == len(created_fils)


#######################
## REPORT GENERATION ##
#######################


@pytest.fixture(scope="session")
def generate_report() -> Iterable[None]:
    # creates report after running benchmark tests
    yield
    _render_report()
    print(f"please open report found at {_REPORT}")


_REPORT: Path = CURRENT_DIR / "report.ignore.md"

SessionId: TypeAlias = str
Reason: TypeAlias = str
FromTo: TypeAlias = str


class GroupMap(TypedDict):
    session_id: SessionId
    reason: Reason
    from_to: FromTo
    item: MetricsResult


def __group_by_keys(
    data: list[GroupMap], group_keys: tuple[str, ...]
) -> dict[tuple[str, ...], list[MetricsResult]]:
    # Sort the data based on the group keys
    data.sort(key=lambda x: [x[key] for key in group_keys])

    # Group the data by the specified keys
    grouped_data = groupby(data, key=lambda x: tuple(x[key] for key in group_keys))

    return {key: [x["item"] for x in group] for key, group in grouped_data}


def __get_grouping_map(metrics_results: list[MetricsResult]) -> list[GroupMap]:
    # NOTE: if more fields are required for grouping,
    # extend the GroupMap model and add them below
    return [
        GroupMap(
            session_id=entry.session_id,
            reason=entry.tags["reason"],
            from_to=entry.tags["from"] + " -> " + entry.tags["to"],
            item=entry,
        )
        for entry in metrics_results
    ]


def _group_by_session_id_and_description(
    metrics_results: list[MetricsResult],
) -> dict[tuple[SessionId, Reason], list[MetricsResult]]:
    grouped_results: dict[
        tuple[SessionId, Reason], list[MetricsResult]
    ] = __group_by_keys(
        __get_grouping_map(metrics_results), group_keys=("session_id", "reason")
    )
    return grouped_results


def _group_by_from_to_key(
    metrics_results: list[MetricsResult],
) -> dict[tuple[FromTo], list[MetricsResult]]:
    grouped_results: dict[
        tuple[SessionId, Reason], list[MetricsResult]
    ] = __group_by_keys(__get_grouping_map(metrics_results), group_keys=("from_to",))
    return grouped_results


_TEMPLATE_REPORT_SECTION = """
### Test Session {session_id}

Reason `{reason}` data query `{query}`

{rendered_table}

"""


def _flip_list_matrix(matrix: list[list[Any]]) -> list[list[Any]]:
    r_count = len(matrix)
    c_count = len(matrix[0])

    new_matrix = [["" for _ in range(r_count)] for _ in range(c_count)]

    for ir, r in enumerate(matrix):
        for ic, element in enumerate(r):
            new_matrix[ic][ir] = element

    return new_matrix


def _render_report() -> None:
    # Data divided in:
    # group by sessions_id
    #   -> group by reason
    #       -> group by subdivide by "[from] -> [to]"
    #           -> list entries here

    metrics_results = parse_file_as(list[MetricsResult], _TEST_RESULTS)

    def _render_table(table_data: list[list[str]]) -> str:
        def _render_row(data: Iterable) -> str:
            return "|" + "|".join(map(str, data)) + "|\n"

        result = ""
        for k, row in enumerate(table_data):
            result += _render_row(row)
            if k == 0:
                dahs_items = ["-" for _ in range(len(row))]
                result += _render_row(dahs_items)
        return result

    file_content = ""

    for (session_id, reason), g1_items in _group_by_session_id_and_description(
        metrics_results
    ).items():
        table_data: list[list[str]] = []

        HEADERS = [
            "S3 Backend",
            "Total queried files",
            "Worst (ms)",
            "Average (ms)",
            "Best (ms)",
        ]
        table_data.append(HEADERS)

        for (from_to_key,), g2_items in _group_by_from_to_key(g1_items).items():
            all_times = [x.duration_ms for x in g2_items]

            worst = max(all_times)
            average = sum(all_times) / len(all_times)
            best = min(all_times)

            file_count = g2_items[0].tags["generated_file_count"]

            row = [
                from_to_key,
                file_count,
                f"{worst:.2f}",
                f"{average:.2f}",
                f"{best:.2f}",
            ]
            assert len(row) == len(HEADERS)
            table_data.append(row)

        rendered_table = _render_table(_flip_list_matrix(table_data))

        query = g1_items[0].tags["query"]

        rendered_report_section = _TEMPLATE_REPORT_SECTION.format(
            session_id=session_id,
            reason=reason,
            query=query,
            rendered_table=rendered_table,
        )
        file_content += rendered_report_section

    _REPORT.write_text(file_content)


if __name__ == "__main__":
    # use this to generate a report after the benchmark tests have been ran
    if not _TEST_RESULTS.exists():
        print(
            "First run the following\npytest tests/unit/test_handlers_simcore_s3_benchmark.py"
        )
        sys.exit(1)
    _render_report()
