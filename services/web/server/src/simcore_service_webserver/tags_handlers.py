import sqlalchemy as sa
from aiohttp import web
from servicelib.aiohttp.application_keys import APP_DB_ENGINE_KEY
from simcore_postgres_database.models.groups import groups, user_to_groups
from simcore_postgres_database.models.tags import tags, tags_to_groups
from simcore_postgres_database.models.users import users

from .login.decorators import RQT_USERID_KEY, login_required
from .security_api import check_permission


@login_required
async def list_tags(request: web.Request):
    await check_permission(request, "tag.crud.*")
    uid, engine = request[RQT_USERID_KEY], request.app[APP_DB_ENGINE_KEY]

    # select read tags in user's groups
    j_user_read_tags = (
        tags.join(
            tags_to_groups,
            (tags.c.tag_id == tags_to_groups.c.id) & (tags_to_groups.c.read == True),
        )
        .join(groups)
        .join(user_to_groups, user_to_groups.c.uid == uid)
    )
    select_stmt = (
        sa.select([tags.c.id, tags.c.name, tags.c.description, tags.c.color])
        .distinct(tags.c.id)
        .select_from(j_user_read_tags)
        .order_by(tags.c.name)
        .limit(50)
    )

    async with engine.acquire() as conn:
        # pylint: disable=not-an-iterable
        result = []
        async for row in conn.execute(select_stmt):
            row_dict = dict(row.items())
            result.append(row_dict)
    return result


@login_required
async def update_tag(request: web.Request):
    await check_permission(request, "tag.crud.*")
    uid, engine = request[RQT_USERID_KEY], request.app[APP_DB_ENGINE_KEY]
    tag_id = request.match_info.get("tag_id")
    tag_data = await request.json()

    # select write tags in user's groups
    j_user_write_tags = (
        tags.join(
            tags_to_groups,
            (tags.c.id == tag_id) & (tags_to_groups.c.write == True),
        )
        .join(groups)
        .join(user_to_groups, (user_to_groups.c.uid == uid))
    )

    update_stmt = (
        tags.update()
        .values(
            name=tag_data["name"],
            description=tag_data["description"],
            color=tag_data["color"],
        )
        .where((tags.c.id == tag_id) & (tags.c.user_id == uid))
        .returning(tags.c.id, tags.c.name, tags.c.description, tags.c.color)
    )

    async with engine.acquire() as conn:
        if can_update := await conn.scalar(
            sa.select([tags_to_groups.write]).select_from(j_user_write_tags).distinct()
        ):
            assert can_update  # nosec
            result = await conn.execute(update_stmt)
            if row_proxy := await result.first():
                return dict(row_proxy.items())

        raise web.HTTPInternalServerError()


@login_required
async def create_tag(request: web.Request):
    await check_permission(request, "tag.crud.*")
    uid, engine = request[RQT_USERID_KEY], request.app[APP_DB_ENGINE_KEY]
    tag_data = await request.json()

    # repository
    insert_tag_stmt = (
        tags.insert()
        .values(
            name=tag_data["name"],
            description=tag_data["description"],
            color=tag_data["color"],
        )
        .returning(tags.c.id, tags.c.name, tags.c.description, tags.c.color)
    )

    async with engine.acquire() as conn:
        async with conn.begin():
            # get primary gid
            primary_gid = await conn.scalar(
                sa.select([users.c.primary_gid]).where(users.c.id == uid)
            )

            # insert new tag
            result = await conn.execute(insert_tag_stmt)
            if tag := await result.first():
                # take tag ownership
                await conn.execute(
                    tags_to_groups.insert().values(
                        tag_id=tag.id,
                        group_id=primary_gid,
                        read=True,
                        write=True,
                        delete=True,
                    )
                )
                return dict(tag.items())

    raise web.HTTPInternalServerError()


@login_required
async def delete_tag(request: web.Request):
    await check_permission(request, "tag.crud.*")
    uid, engine = request[RQT_USERID_KEY], request.app[APP_DB_ENGINE_KEY]
    tag_id = request.match_info.get("tag_id")

    # select delete tags in user's groups
    j_user_delete_tags = (
        tags.join(
            tags_to_groups,
            (tags.c.id == tag_id) & (tags_to_groups.c.delete == True),
        )
        .join(groups)
        .join(user_to_groups, (user_to_groups.c.uid == uid))
    )

    async with engine.acquire() as conn:
        # pylint: disable=no-value-for-parameter
        if can_delete := await conn.scalar(
            sa.select([tags_to_groups.delete])
            .select_from(j_user_delete_tags)
            .distinct()
        ):
            assert can_delete  # nosec
            async with conn.execute(tags.delete().where(tags.c.id == tag_id)):
                raise web.HTTPNoContent(content_type="application/json")

    raise web.HTTPInternalServerError()
    # FIXME: access error if cannot delete?
