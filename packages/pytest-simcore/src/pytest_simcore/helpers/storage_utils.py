import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypedDict

import sqlalchemy as sa
from faker import Faker
from models_library.basic_types import SHA256Str
from pydantic import ByteSize
from simcore_postgres_database.storage_models import projects
from sqlalchemy.ext.asyncio import AsyncEngine

log = logging.getLogger(__name__)


def has_datcore_tokens() -> bool:
    api_key = os.environ.get("BF_API_KEY")
    api_secret = os.environ.get("BF_API_SECRET")
    if not api_key or not api_secret:
        return False
    return not (api_key == "none" or api_secret == "none")  # noqa: S105


async def get_updated_project(
    sqlalchemy_async_engine: AsyncEngine, project_id: str
) -> dict[str, Any]:
    async with sqlalchemy_async_engine.connect() as conn:
        result = await conn.execute(
            sa.select(projects).where(projects.c.uuid == project_id)
        )
        row = result.one()
        return row._asdict()


class FileIDDict(TypedDict):
    path: Path
    sha256_checksum: SHA256Str


@dataclass(frozen=True, kw_only=True, slots=True)
class ProjectWithFilesParams:
    num_nodes: int
    allowed_file_sizes: tuple[ByteSize, ...]
    workspace_files_count: int
    allowed_file_checksums: tuple[SHA256Str, ...] = None  # type: ignore # NOTE: OK for testing

    def __post_init__(self):
        if self.allowed_file_checksums is None:
            # generate some random checksums for the corresponding file sizes
            faker = Faker()
            checksums = tuple(faker.sha256() for _ in self.allowed_file_sizes)
            object.__setattr__(self, "allowed_file_checksums", checksums)

    def __repr__(self) -> str:
        return f"ProjectWithFilesParams: #nodes={self.num_nodes}, file sizes={[_.human_readable() for _ in self.allowed_file_sizes]}"
