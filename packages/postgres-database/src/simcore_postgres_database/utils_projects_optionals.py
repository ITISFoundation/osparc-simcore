import sqlalchemy as sa
from aiopg.sa.connection import SAConnection

from .models.projects_optionals import projects_optionals


class CouldNotCreateOrUpdateUserPreferenceError(Exception): ...


class BasePreferencesRepo:
    model: sa.Table = projects_optionals

    @classmethod
    async def allows_guests_to_push_states_and_output_ports(
        cls, connection: SAConnection, *, project_uuid: str
    ) -> bool:
        result: bool | None = await connection.scalar(
            sa.select(cls.model.c.allow_guests_to_push_states_and_output_ports).where(
                cls.model.c.project_uuid == project_uuid
            )
        )
        return result if result is not None else False

    @classmethod
    async def set_allow_guests_to_push_states_and_output_ports(
        cls, connection: SAConnection, *, project_uuid: str
    ) -> None:
        await connection.execute(
            sa.insert(projects_optionals).values(
                project_uuid=project_uuid,
                allow_guests_to_push_states_and_output_ports=True,
            )
        )
