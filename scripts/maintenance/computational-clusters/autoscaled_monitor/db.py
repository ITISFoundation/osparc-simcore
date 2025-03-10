import asyncio
import contextlib
import uuid
from collections.abc import AsyncGenerator
from typing import Any

import rich
import sqlalchemy as sa
from pydantic import PostgresDsn, TypeAdapter
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from .models import AppState, ComputationalTask, PostgresDB
from .ssh import ssh_tunnel


@contextlib.asynccontextmanager
async def db_engine(
    state: AppState,
) -> AsyncGenerator[AsyncEngine, Any]:
    async with contextlib.AsyncExitStack() as stack:
        assert state.environment["POSTGRES_ENDPOINT"]  # nosec
        db_endpoint = state.environment["POSTGRES_ENDPOINT"]
        if state.main_bastion_host:
            assert state.ssh_key_path  # nosec
            db_host, db_port = db_endpoint.split(":")
            tunnel = stack.enter_context(
                ssh_tunnel(
                    ssh_host=state.main_bastion_host.ip,
                    username=state.main_bastion_host.user_name,
                    private_key_path=state.ssh_key_path,
                    remote_bind_host=db_host,
                    remote_bind_port=int(db_port),
                )
            )
            assert tunnel
            db_endpoint = (
                f"{tunnel.local_bind_address[0]}:{tunnel.local_bind_address[1]}"
            )

        engine = None
        try:
            for env in [
                "POSTGRES_USER",
                "POSTGRES_PASSWORD",
                "POSTGRES_DB",
            ]:
                assert state.environment[env]
            postgres_db = PostgresDB(
                dsn=TypeAdapter(PostgresDsn).validate_python(
                    f"postgresql+asyncpg://{state.environment['POSTGRES_USER']}:{state.environment['POSTGRES_PASSWORD']}@{db_endpoint}/{state.environment['POSTGRES_DB']}"
                )
            )

            engine = create_async_engine(
                f"{postgres_db.dsn}",
                connect_args={
                    "server_settings": {
                        "application_name": "osparc-clusters-monitoring-script"
                    }
                },
            )
            yield engine
        finally:
            if engine:
                await engine.dispose()


async def abort_job_in_db(
    state: AppState, project_id: uuid.UUID, node_id: uuid.UUID
) -> None:
    async with contextlib.AsyncExitStack() as stack:
        engine = await stack.enter_async_context(db_engine(state))
        db_connection = await stack.enter_async_context(engine.begin())

        await db_connection.execute(
            sa.text(
                f"UPDATE comp_tasks SET state = 'ABORTED' WHERE project_id='{project_id}' AND node_id='{node_id}'"
            )
        )
        rich.print(f"set comp_tasks for {project_id=}/{node_id=} set to ABORTED")


async def check_db_connection(state: AppState) -> bool:
    try:
        async with contextlib.AsyncExitStack() as stack:
            engine = await stack.enter_async_context(db_engine(state))
            async with asyncio.timeout(5):
                db_connection = await stack.enter_async_context(engine.connect())
                result = await db_connection.execute(sa.text("SELECT 1"))
            result.one()
            rich.print(
                "[green]Database connection test completed successfully![/green]"
            )
            return True
    except Exception as e:  # pylint: disable=broad-exception-caught
        rich.print(f"[red]Database connection test failed: {e}[/red]")
    return False


async def list_computational_tasks_from_db(
    state: AppState, user_id: int
) -> list[ComputationalTask]:
    async with contextlib.AsyncExitStack() as stack:
        engine = await stack.enter_async_context(db_engine(state))
        db_connection = await stack.enter_async_context(engine.begin())

        # Get the list of running project UUIDs with a subquery
        subquery = (
            sa.select(sa.column("project_uuid"))
            .select_from(sa.table("comp_runs"))
            .where(
                sa.and_(
                    sa.column("user_id") == user_id,
                    sa.cast(sa.column("result"), sa.VARCHAR) != "SUCCESS",
                    sa.cast(sa.column("result"), sa.VARCHAR) != "FAILED",
                    sa.cast(sa.column("result"), sa.VARCHAR) != "ABORTED",
                )
            )
        )

        # Now select comp_tasks rows where project_id is one of the project_uuids
        query = (
            sa.select("*")
            .select_from(sa.table("comp_tasks"))
            .where(
                sa.column("project_id").in_(subquery)
                & (sa.cast(sa.column("state"), sa.VARCHAR) != "SUCCESS")
                & (sa.cast(sa.column("state"), sa.VARCHAR) != "FAILED")
                & (sa.cast(sa.column("state"), sa.VARCHAR) != "ABORTED")
            )
        )

        result = await db_connection.execute(query)
        comp_tasks_list = result.fetchall()
        return [
            TypeAdapter(ComputationalTask).validate_python(
                {
                    "project_id": row.project_id,
                    "node_id": row.node_id,
                    "job_id": row.job_id,
                    "service_name": row.image["name"].split("/")[-1],
                    "service_version": row.image["tag"],
                    "state": row.state,
                }
            )
            for row in comp_tasks_list
        ]
    msg = "unable to access database!"
    raise RuntimeError(msg)
