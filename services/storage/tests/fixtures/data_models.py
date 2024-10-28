# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from collections import deque
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from random import choice, randint
from typing import Any

import pytest
import sqlalchemy as sa
from aiopg.sa.connection import SAConnection
from aiopg.sa.engine import Engine
from faker import Faker
from models_library.basic_types import SHA256Str
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID, SimcoreS3FileID
from models_library.users import UserID
from pydantic import ByteSize, TypeAdapter
from pytest_simcore.helpers.faker_factories import random_project, random_user
from servicelib.utils import limited_gather
from simcore_postgres_database.models.project_to_groups import project_to_groups
from simcore_postgres_database.storage_models import projects, users
from sqlalchemy.dialects.postgresql import insert as pg_insert

from ..helpers.utils import get_updated_project


@asynccontextmanager
async def _user_context(aiopg_engine: Engine, *, name: str) -> AsyncIterator[UserID]:
    # inject a random user in db

    # NOTE: Ideally this (and next fixture) should be done via webserver API but at this point
    # in time, the webserver service would bring more dependencies to other services
    # which would turn this test too complex.

    # pylint: disable=no-value-for-parameter
    stmt = users.insert().values(**random_user(name=name)).returning(users.c.id)
    async with aiopg_engine.acquire() as conn:
        result = await conn.execute(stmt)
        row = await result.fetchone()
    assert row
    assert isinstance(row.id, int)

    try:
        yield TypeAdapter(UserID).validate_python(row.id)
    finally:
        async with aiopg_engine.acquire() as conn:
            await conn.execute(users.delete().where(users.c.id == row.id))


@pytest.fixture
async def user_id(aiopg_engine: Engine) -> AsyncIterator[UserID]:
    async with _user_context(aiopg_engine, name="test-user") as new_user_id:
        yield new_user_id


@pytest.fixture
async def other_user_id(aiopg_engine: Engine) -> AsyncIterator[UserID]:
    async with _user_context(aiopg_engine, name="test-other-user") as new_user_id:
        yield new_user_id


@pytest.fixture
async def create_project(
    user_id: UserID, aiopg_engine: Engine
) -> AsyncIterator[Callable[[], Awaitable[dict[str, Any]]]]:
    created_project_uuids = []

    async def _creator(**kwargs) -> dict[str, Any]:
        prj_config = {"prj_owner": user_id}
        prj_config.update(kwargs)
        async with aiopg_engine.acquire() as conn:
            result = await conn.execute(
                projects.insert()
                .values(**random_project(**prj_config))
                .returning(sa.literal_column("*"))
            )
            row = await result.fetchone()
            assert row
            created_project_uuids.append(row[projects.c.uuid])
            return dict(row)

    yield _creator
    # cleanup
    async with aiopg_engine.acquire() as conn:
        await conn.execute(
            projects.delete().where(projects.c.uuid.in_(created_project_uuids))
        )


@pytest.fixture
async def create_project_access_rights(
    aiopg_engine: Engine,
) -> AsyncIterator[Callable[[ProjectID, UserID, bool, bool, bool], Awaitable[None]]]:
    _created = []

    async def _creator(
        project_id: ProjectID, user_id: UserID, read: bool, write: bool, delete: bool
    ) -> None:
        async with aiopg_engine.acquire() as conn:
            result = await conn.execute(
                project_to_groups.insert()
                .values(
                    project_uuid=f"{project_id}",
                    gid=sa.select(users.c.primary_gid)
                    .where(users.c.id == f"{user_id}")
                    .scalar_subquery(),
                    read=read,
                    write=write,
                    delete=delete,
                )
                .returning(sa.literal_column("*"))
            )
            row = await result.fetchone()
            assert row
            _created.append(
                (row[project_to_groups.c.project_uuid], row[project_to_groups.c.gid])
            )

    yield _creator

    # cleanup
    async with aiopg_engine.acquire() as conn:
        await conn.execute(
            project_to_groups.delete().where(
                sa.or_(
                    *(
                        (project_to_groups.c.project_uuid == pid)
                        & (project_to_groups.c.gid == gid)
                        for pid, gid in _created
                    )
                )
            )
        )


@pytest.fixture
async def project_id(
    create_project: Callable[[], Awaitable[dict[str, Any]]]
) -> ProjectID:
    project = await create_project()
    return ProjectID(project["uuid"])


@pytest.fixture
async def collaborator_id(aiopg_engine: Engine) -> AsyncIterator[UserID]:

    async with _user_context(aiopg_engine, name="collaborator") as new_user_id:
        yield TypeAdapter(UserID).validate_python(new_user_id)


@pytest.fixture
def share_with_collaborator(
    aiopg_engine: Engine,
    collaborator_id: UserID,
    user_id: UserID,
    project_id: ProjectID,
) -> Callable[[], Awaitable[None]]:
    async def _get_user_group(conn: SAConnection, query_user: int) -> int:
        result = await conn.execute(
            sa.select(users.c.primary_gid).where(users.c.id == query_user)
        )
        row = await result.fetchone()
        assert row
        primary_gid: int = row[users.c.primary_gid]
        return primary_gid

    async def _() -> None:
        async with aiopg_engine.acquire() as conn:
            result = await conn.execute(
                sa.select(projects.c.access_rights).where(
                    projects.c.uuid == f"{project_id}"
                )
            )
            row = await result.fetchone()
            assert row
            access_rights: dict[str | int, Any] = row[projects.c.access_rights]

            access_rights[await _get_user_group(conn, user_id)] = {
                "read": True,
                "write": True,
                "delete": True,
            }
            access_rights[await _get_user_group(conn, collaborator_id)] = {
                "read": True,
                "write": True,
                "delete": False,
            }

            await conn.execute(
                projects.update()
                .where(projects.c.uuid == f"{project_id}")
                .values(access_rights=access_rights)
            )

            # project_to_groups needs to be updated
            for group_id, permissions in access_rights.items():
                insert_stmt = pg_insert(project_to_groups).values(
                    project_uuid=f"{project_id}",
                    gid=int(group_id),
                    read=permissions["read"],
                    write=permissions["write"],
                    delete=permissions["delete"],
                    created=sa.func.now(),
                    modified=sa.func.now(),
                )
                on_update_stmt = insert_stmt.on_conflict_do_update(
                    index_elements=[
                        project_to_groups.c.project_uuid,
                        project_to_groups.c.gid,
                    ],
                    set_={
                        "read": insert_stmt.excluded.read,
                        "write": insert_stmt.excluded.write,
                        "delete": insert_stmt.excluded.delete,
                        "modified": sa.func.now(),
                    },
                )
                await conn.execute(on_update_stmt)

    return _


@pytest.fixture
async def create_project_node(
    user_id: UserID, aiopg_engine: Engine, faker: Faker
) -> Callable[..., Awaitable[NodeID]]:
    async def _creator(
        project_id: ProjectID, node_id: NodeID | None = None, **kwargs
    ) -> NodeID:
        async with aiopg_engine.acquire() as conn:
            result = await conn.execute(
                sa.select(projects.c.workbench).where(
                    projects.c.uuid == f"{project_id}"
                )
            )
            row = await result.fetchone()
            assert row
            project_workbench: dict[str, Any] = row[projects.c.workbench]
            new_node_id = node_id or NodeID(f"{faker.uuid4()}")
            node_data = {
                "key": "simcore/services/frontend/file-picker",
                "version": "1.0.0",
                "label": "pytest_fake_node",
            }
            node_data.update(**kwargs)
            project_workbench.update({f"{new_node_id}": node_data})
            await conn.execute(
                projects.update()
                .where(projects.c.uuid == f"{project_id}")
                .values(workbench=project_workbench)
            )
        return new_node_id

    return _creator


@pytest.fixture
async def random_project_with_files(
    aiopg_engine: Engine,
    create_project: Callable[..., Awaitable[dict[str, Any]]],
    create_project_node: Callable[..., Awaitable[NodeID]],
    create_simcore_file_id: Callable[
        [ProjectID, NodeID, str, Path | None], SimcoreS3FileID
    ],
    upload_file: Callable[..., Awaitable[tuple[Path, SimcoreS3FileID]]],
    faker: Faker,
) -> Callable[
    [int, tuple[ByteSize, ...], tuple[SHA256Str, ...]],
    Awaitable[
        tuple[
            dict[str, Any], dict[NodeID, dict[SimcoreS3FileID, dict[str, Path | str]]]
        ]
    ],
]:
    async def _creator(
        num_nodes: int = 12,
        file_sizes: tuple[ByteSize, ...] = (
            TypeAdapter(ByteSize).validate_python("7Mib"),
            TypeAdapter(ByteSize).validate_python("110Mib"),
            TypeAdapter(ByteSize).validate_python("1Mib"),
        ),
        file_checksums: tuple[SHA256Str, ...] = (
            TypeAdapter(SHA256Str).validate_python(
                "311e2e130d83cfea9c3b7560699c221b0b7f9e5d58b02870bd52b695d8b4aabd"
            ),
            TypeAdapter(SHA256Str).validate_python(
                "08e297db979d3c84f6b072c2a1e269e8aa04e82714ca7b295933a0c9c0f62b2e"
            ),
            TypeAdapter(SHA256Str).validate_python(
                "488f3b57932803bbf644593bd46d95599b1d4da1d63bc020d7ebe6f1c255f7f3"
            ),
        ),
    ) -> tuple[
        dict[str, Any], dict[NodeID, dict[SimcoreS3FileID, dict[str, Path | str]]]
    ]:
        assert len(file_sizes) == len(file_checksums)
        project = await create_project(name="random-project")
        src_projects_list: dict[
            NodeID, dict[SimcoreS3FileID, dict[str, Path | str]]
        ] = {}
        upload_tasks: deque[Awaitable] = deque()
        for _node_index in range(num_nodes):
            # NOTE: we put some more outputs in there to simulate a real case better
            new_node_id = NodeID(f"{faker.uuid4()}")
            output3_file_id = create_simcore_file_id(
                ProjectID(project["uuid"]),
                new_node_id,
                faker.file_name(),
                Path("outputs/output3"),
            )
            src_node_id = await create_project_node(
                ProjectID(project["uuid"]),
                new_node_id,
                outputs={
                    "output_1": faker.pyint(),
                    "output_2": faker.pystr(),
                    "output_3": f"{output3_file_id}",
                },
            )
            assert src_node_id == new_node_id

            # upload the output 3 and some random other files at the root of each node
            src_projects_list[src_node_id] = {}
            checksum: SHA256Str = choice(file_checksums)  # noqa: S311
            src_file, _ = await upload_file(
                file_size=choice(file_sizes),  # noqa: S311
                file_name=Path(output3_file_id).name,
                file_id=output3_file_id,
                sha256_checksum=checksum,
            )
            src_projects_list[src_node_id][output3_file_id] = {
                "path": src_file,
                "sha256_checksum": checksum,
            }

            async def _upload_file_and_update_project(project, src_node_id):
                src_file_name = faker.file_name()
                src_file_uuid = create_simcore_file_id(
                    ProjectID(project["uuid"]), src_node_id, src_file_name, None
                )
                checksum: SHA256Str = choice(file_checksums)  # noqa: S311
                src_file, _ = await upload_file(
                    file_size=choice(file_sizes),  # noqa: S311
                    file_name=src_file_name,
                    file_id=src_file_uuid,
                    sha256_checksum=checksum,
                )
                src_projects_list[src_node_id][src_file_uuid] = {
                    "path": src_file,
                    "sha256_checksum": checksum,
                }

            # add a few random files in the node storage
            upload_tasks.extend(
                [
                    _upload_file_and_update_project(project, src_node_id)
                    for _ in range(randint(0, 3))  # noqa: S311
                ]
            )
        await limited_gather(*upload_tasks, limit=10)

        project = await get_updated_project(aiopg_engine, project["uuid"])
        return project, src_projects_list

    return _creator
