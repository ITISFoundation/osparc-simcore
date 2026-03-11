import asyncio
import contextlib
import uuid
from collections.abc import AsyncGenerator
from typing import Any

import rich
import sqlalchemy as sa
from pydantic import PostgresDsn, TypeAdapter
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from .models import AppState, ComputationalTask, PostgresDB, ResourceTrackerServiceRun
from .ssh import ssh_tunnel


@contextlib.asynccontextmanager
async def db_engine(
    state: AppState,
) -> AsyncGenerator[AsyncEngine, Any]:
    async with contextlib.AsyncExitStack() as stack:
        assert state.environment["POSTGRES_HOST"]  # nosec
        assert state.environment["POSTGRES_PORT"]  # nosec
        db_endpoint = f"{state.environment['POSTGRES_HOST']}:{state.environment['POSTGRES_PORT']}"
        if state.main_bastion_host:
            assert state.ssh_key_path  # nosec
            db_host, db_port = db_endpoint.split(":")
            host, port = await stack.enter_async_context(
                ssh_tunnel(
                    ssh_host=state.main_bastion_host.ip,
                    username=state.main_bastion_host.user_name,
                    private_key_path=state.ssh_key_path,
                    remote_bind_host=db_host,
                    remote_bind_port=int(db_port),
                )
            )
            db_endpoint = f"{host}:{port}"

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
                connect_args={"server_settings": {"application_name": "osparc-clusters-monitoring-script"}},
            )
            yield engine
        finally:
            if engine:
                await engine.dispose()


async def abort_job_in_db(engine: AsyncEngine, project_id: uuid.UUID, node_id: uuid.UUID) -> None:
    async with engine.begin() as db_connection:
        await db_connection.execute(
            sa.update(sa.table("comp_tasks"))
            .where(
                sa.and_(
                    sa.column("project_id") == str(project_id),
                    sa.column("node_id") == str(node_id),
                )
            )
            .values(state="ABORTED")
        )
        rich.print(f"set comp_tasks for {project_id=}/{node_id=} set to ABORTED")


async def check_db_connection(state: AppState) -> bool:
    try:
        async with db_engine(state) as engine:
            async with asyncio.timeout(5):
                async with engine.connect() as db_connection:
                    result = await db_connection.execute(sa.select(sa.literal(1)))
                result.one()
                rich.print("[green]Database connection test completed successfully![/green]")
                return True
    except Exception as e:  # pylint: disable=broad-exception-caught
        rich.print(f"[red]Database connection test failed: {e}[/red]")
    return False


async def list_computational_tasks_from_db(engine: AsyncEngine, user_id: int) -> list[ComputationalTask]:
    async with engine.begin() as db_connection:
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


async def list_resource_tracker_running_computational_services(
    engine: AsyncEngine,
) -> list[ResourceTrackerServiceRun]:
    """Return all RUNNING COMPUTATIONAL_SERVICE entries from resource_tracker_service_runs."""
    async with engine.begin() as db_connection:
        query = (
            sa.select(
                sa.column("service_run_id"),
                sa.column("user_id"),
                sa.column("wallet_id"),
                sa.column("product_name"),
                sa.column("project_id"),
                sa.column("node_id"),
                sa.column("service_key"),
                sa.column("service_version"),
                sa.column("started_at"),
                sa.column("last_heartbeat_at"),
                sa.column("missed_heartbeat_counter"),
                sa.column("pricing_unit_cost"),
            )
            .select_from(sa.table("resource_tracker_service_runs"))
            .where(
                sa.and_(
                    sa.cast(sa.column("service_run_status"), sa.VARCHAR) == "RUNNING",
                    sa.cast(sa.column("service_type"), sa.VARCHAR) == "COMPUTATIONAL_SERVICE",
                )
            )
        )
        result = await db_connection.execute(query)
        rows = result.fetchall()
        return [
            ResourceTrackerServiceRun(
                service_run_id=row.service_run_id,
                user_id=row.user_id,
                wallet_id=row.wallet_id,
                product_name=row.product_name,
                project_id=row.project_id,
                node_id=row.node_id,
                service_key=row.service_key,
                service_version=row.service_version,
                started_at=row.started_at,
                last_heartbeat_at=row.last_heartbeat_at,
                missed_heartbeat_counter=row.missed_heartbeat_counter,
                pricing_unit_cost=float(row.pricing_unit_cost) if row.pricing_unit_cost is not None else None,
            )
            for row in rows
        ]


async def get_user_and_wallet_info(
    engine: AsyncEngine,
    user_id: int,
    wallet_id: int | None,
) -> tuple[str | None, str | None]:
    """Returns (user_email, wallet_name)."""
    async with engine.connect() as db_connection:
        email: str | None = None
        wallet_name: str | None = None

        result = await db_connection.execute(
            sa.select(sa.column("email")).select_from(sa.table("users")).where(sa.column("id") == user_id)
        )
        row = result.fetchone()
        if row:
            email = str(row.email)

        if wallet_id is not None:
            result = await db_connection.execute(
                sa.select(sa.column("name")).select_from(sa.table("wallets")).where(sa.column("wallet_id") == wallet_id)
            )
            row = result.fetchone()
            if row:
                wallet_name = str(row.name)

        return email, wallet_name


async def get_product_usd_per_credit(
    engine: AsyncEngine,
    product_name: str,
) -> float | None:
    """Returns the latest usd_per_credit for the product, or None if not found/zero."""
    async with engine.connect() as db_connection:
        result = await db_connection.execute(
            sa.select(sa.column("usd_per_credit"))
            .select_from(sa.table("products_prices"))
            .where(sa.column("product_name") == product_name)
            .order_by(sa.column("valid_from").desc())
            .limit(1)
        )
        row = result.fetchone()
        if row and row.usd_per_credit is not None:
            value = float(row.usd_per_credit)
            return value if value > 0 else None
        return None
