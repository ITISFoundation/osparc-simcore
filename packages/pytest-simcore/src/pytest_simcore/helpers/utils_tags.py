# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from aiopg.sa.connection import SAConnection
from simcore_postgres_database.models.tags import tags, tags_to_groups


async def create_tag_access(
    conn: SAConnection,
    *,
    tag_id,
    group_id,
    read,
    write,
    delete,
) -> int:
    await conn.execute(
        tags_to_groups.insert().values(
            tag_id=tag_id, group_id=group_id, read=read, write=write, delete=delete
        )
    )
    return tag_id


async def create_tag(
    conn: SAConnection,
    *,
    name,
    description,
    color,
    group_id,
    read,
    write,
    delete,
) -> int:
    """helper to create a tab by inserting rows in two different tables"""
    tag_id = await conn.scalar(
        tags.insert()
        .values(name=name, description=description, color=color)
        .returning(tags.c.id)
    )
    assert tag_id
    await create_tag_access(
        conn, tag_id=tag_id, group_id=group_id, read=read, write=write, delete=delete
    )
    return tag_id


async def delete_tag(conn: SAConnection, tag_id: int):
    await conn.execute(tags.delete().where(tags.c.id == tag_id))
