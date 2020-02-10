"""this module creates a background task that monitors changes in the database.
First a procedure is registered in postgres that gets triggered whenever the outputs
of a record in comp_task table is changed.
"""

import asyncio
import json
import logging

from aiohttp import web
from aiopg.sa import Engine
from sqlalchemy.sql import select

from servicelib.application_keys import APP_DB_ENGINE_KEY

from .projects import projects_api
from .projects.projects_models import projects, user_to_projects

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
    CREATE TRIGGER {DB_TRIGGER_NAME}
    AFTER UPDATE OF outputs ON comp_tasks
        FOR EACH ROW
        WHEN (OLD.outputs::jsonb IS DISTINCT FROM NEW.outputs::jsonb)
        EXECUTE PROCEDURE {DB_PROCEDURE_NAME}();
    """
    async with db_engine.acquire() as conn:
        async with conn.begin():
            await conn.execute(notification_fct_query)
            await conn.execute(trigger_registration_query)
        

async def unregister(app: web.Application) -> None:
    drop_trigger_query = f"""
    DROP TRIGGER {DB_TRIGGER_NAME} on comp_tasks;
    """

    db_engine: Engine = app[APP_DB_ENGINE_KEY]
    async with db_engine.acquire() as conn:
        async with conn.begin():
            await conn.execute(drop_trigger_query)

async def listen(app: web.Application):
    listen_query = f"LISTEN {DB_CHANNEL_NAME}"
    db_engine: Engine = app[APP_DB_ENGINE_KEY]
    async with db_engine.acquire() as conn:
        async with conn.begin():
            await conn.execute(listen_query)
            msg = await conn.connection.notifies.get()
            log.debug("DB comp_tasks.outputs Update: <- %s", msg.payload)
            node = json.loads(msg.payload)
            node_data = node["data"]
            task_output = node_data["outputs"]
            node_id = node_data["node_id"]
            project_id = node_data["project_id"]
            # find the user(s) linked to that project (why do I need to know the user?)
            joint_table = user_to_projects.join(projects)
            query = select([user_to_projects]).select_from(joint_table).where(projects.c.uuid == project_id)
            async for row in conn.execute(query):
                user_id = row["user_id"]
                node_data = await projects_api.update_project_node_outputs(app, user_id, project_id, node_id, data=task_output)
                #FIXME: this is not the final version
                from .computation_subscribe import post_messages
                messages = {"nodeUpdated": {"Node": node_id, "Data": node_data}}
                await post_messages(app, user_id, messages)
        

async def comp_tasks_listening_task(app: web.Application) -> None:
    log.info("starting comp_task db listening task...")
    try:
        await register_trigger_function(app)
        log.info("listening to comp_task events...")
        while True:
            await listen(app)
    except asyncio.CancelledError:
        pass
    finally:
        await unregister(app)

async def setup_comp_tasks_listening_task(app: web.Application):
    task = asyncio.get_event_loop().create_task(comp_tasks_listening_task(app))
    yield
    task.cancel()
    await task


def setup(app: web.Application):
    app.cleanup_ctx.append(setup_comp_tasks_listening_task)
