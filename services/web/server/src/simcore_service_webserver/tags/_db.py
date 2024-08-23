import sqlalchemy as sa
from aiopg.sa.connection import SAConnection
from simcore_postgres_database.models.projects_tags import projects_tags
from simcore_postgres_database.tags_repo import TagsRepo
from sqlalchemy.dialects.postgresql import insert as pg_insert

#
# TODO: TagsRepo here ?? and move the tests here as well??
#

assert TagsRepo

#
# TODO: Extends TagsRepo into ProjectTagsRepo, ServicesTagsRepo ??
#


class ProjectTagsRepo:
    @staticmethod
    async def get_tags_by_project(conn: SAConnection, project_id: str) -> list:
        stmt = sa.select(projects_tags.c.tag_id).where(
            projects_tags.c.project_id == project_id
        )
        return [row.tag_id async for row in conn.execute(stmt)]

    @staticmethod
    async def _upsert_tags_in_project(
        conn: SAConnection, project_index_id: int, project_tags: list[int]
    ) -> None:
        for tag_id in project_tags:
            await conn.execute(
                pg_insert(projects_tags)
                .values(
                    project_id=project_index_id,
                    tag_id=tag_id,
                )
                .on_conflict_do_nothing()
            )


# Q: what happens if tags are disabled?
# Does this mean that the functionality is not available?
#
