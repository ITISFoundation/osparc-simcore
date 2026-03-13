import asyncio
import contextlib
import uuid
from collections.abc import AsyncGenerator
from typing import Any

import rich
import sqlalchemy as sa
from aiocache import cached
from pydantic import PostgresDsn, TypeAdapter
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from .models import (
    AppState,
    ComputationalTask,
    DynamicServiceExtraInfo,
    PostgresDB,
    ResourceTrackerServiceRun,
)
from .ssh import ssh_tunnel


def _build_key(fn, *args, **kwargs):
    """Cache key builder that skips the first arg (engine)."""
    return f"{fn.__module__}.{fn.__name__}:{args[1:]}:{kwargs}"


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
                    bastion_conn=None,
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


async def abort_jobs_in_db(engine: AsyncEngine, project_node_ids: set[tuple[uuid.UUID, uuid.UUID]]) -> None:
    async with engine.begin() as db_connection:
        await db_connection.execute(
            sa.update(sa.table("comp_tasks"))
            .where(
                sa.tuple_(sa.column("project_id"), sa.column("node_id")).in_(
                    [(str(pid), str(nid)) for pid, nid in project_node_ids]
                )
            )
            .values(state="ABORTED")
        )
    rich.print(f"set comp_tasks for {project_node_ids=} set to ABORTED")


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


@cached(key_builder=_build_key)
async def list_computational_tasks_from_db(engine: AsyncEngine, user_id: int) -> list[ComputationalTask]:
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

    async with engine.begin() as conn:
        result = await conn.execute(query)
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


@cached(key_builder=_build_key)
async def list_resource_tracker_running_computational_services(
    engine: AsyncEngine,
) -> list[ResourceTrackerServiceRun]:
    """Return all RUNNING COMPUTATIONAL_SERVICE entries from resource_tracker_service_runs."""
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
            sa.column("simcore_user_agent"),
        )
        .select_from(sa.table("resource_tracker_service_runs"))
        .where(
            sa.and_(
                sa.cast(sa.column("service_run_status"), sa.VARCHAR) == "RUNNING",
                sa.cast(sa.column("service_type"), sa.VARCHAR) == "COMPUTATIONAL_SERVICE",
            )
        )
    )
    async with engine.connect() as conn:
        result = await conn.execute(query)
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
            simcore_user_agent=row.simcore_user_agent,
        )
        for row in rows
    ]


@cached(key_builder=_build_key)
async def get_user_and_wallet_info(
    engine: AsyncEngine,
    user_id: int,
    wallet_id: int | None,
) -> tuple[str | None, str | None, str | None]:
    """Returns (user_email, wallet_name, product_name)."""
    email: str | None = None
    wallet_name: str | None = None
    product_name: str | None = None

    async with engine.connect() as conn:
        result = await conn.execute(
            sa.select(sa.column("email")).select_from(sa.table("users")).where(sa.column("id") == user_id)
        )
        row = result.fetchone()
        if row:
            email = str(row.email)

        if wallet_id is not None:
            result = await conn.execute(
                sa.select(sa.column("name"), sa.column("product_name"))
                .select_from(sa.table("wallets"))
                .where(sa.column("wallet_id") == wallet_id)
            )
            row = result.fetchone()
            if row:
                wallet_name = str(row.name)
                product_name = str(row.product_name)

    return email, wallet_name, product_name


async def get_dynamic_service_extra_info(
    engine: AsyncEngine,
    services: list[tuple[int, str, str]],
) -> dict[tuple[str, str], DynamicServiceExtraInfo]:
    """Resolve email, wallet and RUT info for dynamic services.

    Args:
        engine: async DB engine
        services: list of (user_id, project_id, node_id) tuples

    Returns:
        mapping (project_id, node_id) -> DynamicServiceExtraInfo
    """
    if not services:
        return {}

    unique_user_ids = {uid for uid, _, _ in services}

    async with engine.connect() as conn:
        # Batch-fetch user emails
        user_emails: dict[int, str | None] = {}
        if unique_user_ids:
            result = await conn.execute(
                sa.select(sa.column("id"), sa.column("email"))
                .select_from(sa.table("users"))
                .where(sa.column("id").in_(unique_user_ids))
            )
            for row in result.fetchall():
                user_emails[row.id] = str(row.email)

        # Fetch RUT entries for DYNAMIC_SERVICE
        rut_by_key: dict[tuple[str, str], ResourceTrackerServiceRun] = {}
        result = await conn.execute(
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
                sa.column("simcore_user_agent"),
            )
            .select_from(sa.table("resource_tracker_service_runs"))
            .where(
                sa.and_(
                    sa.cast(sa.column("service_run_status"), sa.VARCHAR) == "RUNNING",
                    sa.cast(sa.column("service_type"), sa.VARCHAR) == "DYNAMIC_SERVICE",
                    sa.tuple_(sa.column("project_id"), sa.column("node_id")).in_(
                        [(str(pid), str(nid)) for _, pid, nid in services]
                    ),
                )
            )
        )
        for row in result.fetchall():
            rut_by_key[(str(row.project_id), str(row.node_id))] = ResourceTrackerServiceRun(
                service_run_id=row.service_run_id,
                user_id=row.user_id,
                wallet_id=row.wallet_id,
                product_name=row.product_name,
                project_id=str(row.project_id),
                node_id=str(row.node_id),
                service_key=row.service_key,
                service_version=row.service_version,
                started_at=row.started_at,
                last_heartbeat_at=row.last_heartbeat_at,
                missed_heartbeat_counter=row.missed_heartbeat_counter,
                pricing_unit_cost=float(row.pricing_unit_cost) if row.pricing_unit_cost is not None else None,
                simcore_user_agent=row.simcore_user_agent,
            )

        # Batch-fetch wallet names
        unique_wallet_ids = {r.wallet_id for r in rut_by_key.values() if r.wallet_id is not None}
        wallet_names: dict[int, str | None] = {}
        if unique_wallet_ids:
            result = await conn.execute(
                sa.select(sa.column("wallet_id"), sa.column("name"))
                .select_from(sa.table("wallets"))
                .where(sa.column("wallet_id").in_(unique_wallet_ids))
            )
            for row in result.fetchall():
                wallet_names[row.wallet_id] = str(row.name)

        # Batch-fetch usd_per_credit per product
        unique_products = {r.product_name for r in rut_by_key.values()}
        product_usd: dict[str, float | None] = {}
        for product in unique_products:
            product_usd[product] = await _get_product_usd_per_credit(conn, product)

    # Build final mapping
    info: dict[tuple[str, str], DynamicServiceExtraInfo] = {}
    for uid, pid, nid in services:
        rut = rut_by_key.get((pid, nid))
        wid = rut.wallet_id if rut else None
        info[(pid, nid)] = DynamicServiceExtraInfo(
            email=user_emails.get(uid),
            wallet_id=wid,
            wallet_name=wallet_names.get(wid) if wid is not None else None,
            tracker_run=rut,
            usd_per_credit=product_usd.get(rut.product_name) if rut else None,
        )
    return info


async def _get_product_usd_per_credit(
    conn: Any,
    product_name: str,
) -> float | None:
    """Returns the latest usd_per_credit for the product, or None if not found/zero."""
    result = await conn.execute(
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


@cached(key_builder=_build_key)
async def get_product_usd_per_credit(
    engine: AsyncEngine,
    product_name: str,
) -> float | None:
    """Returns the latest usd_per_credit for the product, or None if not found/zero."""
    async with engine.connect() as conn:
        return await _get_product_usd_per_credit(conn, product_name)
