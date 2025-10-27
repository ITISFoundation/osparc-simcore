import sqlalchemy as sa
from simcore_postgres_database.utils_repos import (
    pass_or_acquire_connection,
    transaction_context,
)
from sqlalchemy.ext.asyncio import AsyncEngine

from .models.projects_extensions import projects_extensions


class CouldNotCreateOrUpdateUserPreferenceError(Exception): ...


class ProjectsExtensionsRepo:
    model: sa.Table = projects_extensions

    @classmethod
    async def allows_guests_to_push_states_and_output_ports(
        cls, async_engine: AsyncEngine, *, project_uuid: str
    ) -> bool:
        async with pass_or_acquire_connection(async_engine) as connection:
            result: bool | None = await connection.scalar(
                sa.select(
                    cls.model.c.allow_guests_to_push_states_and_output_ports
                ).where(cls.model.c.project_uuid == project_uuid)
            )
            return result if result is not None else False

    @classmethod
    async def set_allow_guests_to_push_states_and_output_ports(
        cls, async_engine: AsyncEngine, *, project_uuid: str
    ) -> None:
        async with transaction_context(async_engine) as connection:
            await connection.execute(
                sa.insert(projects_extensions).values(
                    project_uuid=project_uuid,
                    allow_guests_to_push_states_and_output_ports=True,
                )
            )
