"""this module creates a background task that monitors changes in the database.
First a procedure is registered in postgres that gets triggered whenever the outputs
of a record in comp_task table is changed.
"""

import asyncio
import json
import logging

from aiohttp import web
from aiopg.sa import Engine
from aiopg.sa.result import RowProxy
from sqlalchemy.sql import select

from servicelib.application_keys import APP_DB_ENGINE_KEY
from simcore_postgres_database.webserver_models import user_to_groups

from .projects import projects_api, projects_exceptions
from .projects.projects_models import projects
from .socketio.events import post_messages

log = logging.getLogger(__name__)

DB_PROCEDURE_NAME: str = "notify_comp_tasks_changed"
DB_TRIGGER_NAME: str = f"{DB_PROCEDURE_NAME}_event"
DB_CHANNEL_NAME: str = "comp_tasks_output_events"


async def register_trigger_function(app: web.Application):
    db_engine: Engine = app[APP_DB_ENGINE_KEY]
    # NOTE: an example was found in https://citizen428.net/blog/asynchronous-notifications-in-postgres/
    notification_fct_query = f"""
    CREATE OR REPLACE FUNCTION {DB_PROCEDURE_NAME}() RETURNS TRIGGER AS $$
        DECLARE
            record RECORD;
            payload JSON;
        BEGIN
            IF (TG_OP = 'DELETE') THEN
                record = OLD;
            ELSE
                record = NEW;
            END IF;

            payload = json_build_object('table', TG_TABLE_NAME,
                                        'action', TG_OP,
                                        'data', row_to_json(record));

            PERFORM pg_notify('{DB_CHANNEL_NAME}', payload::text);

            RETURN NULL;
        END;
    $$ LANGUAGE plpgsql;
    """

    trigger_registration_query = f"""
    DROP TRIGGER IF EXISTS {DB_TRIGGER_NAME} on comp_tasks;
    CREATE TRIGGER {DB_TRIGGER_NAME}
    AFTER UPDATE OF outputs ON comp_tasks
        FOR EACH ROW
        WHEN (OLD.outputs::jsonb IS DISTINCT FROM NEW.outputs::jsonb AND NEW.node_class <> 'FRONTEND')
        EXECUTE PROCEDURE {DB_PROCEDURE_NAME}();
    """

    async with db_engine.acquire() as conn:
        async with conn.begin():
            await conn.execute(notification_fct_query)
            await conn.execute(trigger_registration_query)


async def listen(app: web.Application):
    listen_query = f"LISTEN {DB_CHANNEL_NAME};"
    db_engine: Engine = app[APP_DB_ENGINE_KEY]
    async with db_engine.acquire() as conn:
        await conn.execute(listen_query)
        while True:
            msg = await conn.connection.notifies.get()
            log.debug("DB comp_tasks.outputs Update: <- %s", msg.payload)
            node = json.loads(msg.payload)
            node_data = node["data"]
            task_output = node_data["outputs"]
            node_id = node_data["node_id"]
            project_id = node_data["project_id"]
            # FIXME: we do not know who triggered these changes. we assume the user had the rights to do so
            # therefore we'll use the prj_owner user id. This should be fixed when the new sidecar comes in
            # and comp_tasks/comp_pipeline get deprecated.

            # find the user(s) linked to that project
            result = await conn.execute(
                select([projects]).where(projects.c.uuid == project_id)
            )
            the_project: RowProxy = result.fetchone()
            if not the_project:
                log.warning(
                    "Project %s was not found and cannot be updated", project_id
                )
                continue
            the_project_owner = the_project["prj_owner"]

            # update the project
            try:
                node_data = await projects_api.update_project_node_outputs(
                    app, the_project_owner, project_id, node_id, data=task_output
                )
            except projects_exceptions.ProjectNotFoundError:
                log.warning(
                    "Project %s was not found and cannot be updated", project_id
                )
                continue
            except projects_exceptions.NodeNotFoundError:
                log.warning(
                    "Node %s ib project %s not found and cannot be updated",
                    node_id,
                    project_id,
                )
                continue
            # notify the client(s), the owner + any one with read writes
            clients = [the_project_owner]
            for gid, access_rights in the_project["access_rights"].items():
                if not access_rights["read"]:
                    continue
                # let's get the users in that group
                async for user in conn.execute(
                    select([user_to_groups.c.uid]).where(user_to_groups.c.gid == gid)
                ):
                    clients.append(user["uid"])

            messages = {"nodeUpdated": {"Node": node_id, "Data": node_data}}
            for client in clients:
                await post_messages(app, client, messages)


async def comp_tasks_listening_task(app: web.Application) -> None:
    log.info("starting comp_task db listening task...")
    try:
        await register_trigger_function(app)
        log.info("listening to comp_task events...")
        await listen(app)
    except asyncio.CancelledError:
        pass
    finally:
        pass


async def setup_comp_tasks_listening_task(app: web.Application):
    task = asyncio.get_event_loop().create_task(comp_tasks_listening_task(app))
    yield
    task.cancel()
    await task


def setup(app: web.Application):
    app.cleanup_ctx.append(setup_comp_tasks_listening_task)
