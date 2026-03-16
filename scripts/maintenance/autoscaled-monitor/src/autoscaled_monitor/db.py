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


@cached()
async def list_computational_tasks_by_job_ids(engine: AsyncEngine, job_ids: list[str]) -> list[ComputationalTask]:
    """Fetch computational tasks by specific job IDs.

    Much more efficient than list_computational_tasks_from_db when you already know
    which job_ids you're interested in (e.g., from a cluster's running jobs).
    Uses direct job_id matching instead of scanning all user tasks.

    Args:
        engine: async DB engine
        job_ids: list of job IDs to fetch

    Returns:
        list of ComputationalTask matching the job_ids
    """
    if not job_ids:
        return []

    query = (
        sa.select(
            sa.column("project_id"),
            sa.column("node_id"),
            sa.column("job_id"),
            sa.column("image"),
            sa.column("state"),
        )
        .select_from(sa.table("comp_tasks"))
        .where(sa.column("job_id").in_(job_ids))
    )

    async with engine.connect() as conn:
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


@cached()
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
                sa.column("service_run_status") == "RUNNING",
                sa.column("service_type") == "COMPUTATIONAL_SERVICE",
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


@cached()
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
    """Resolve email, wallet and RUT info for dynamic services using optimized JOINs.

    Args:
        engine: async DB engine
        services: list of (user_id, project_id, node_id) tuples

    Returns:
        mapping (project_id, node_id) -> DynamicServiceExtraInfo
    """
    if not services:
        return {}

    async with engine.connect() as conn:
        # Single optimized query: fetch RUT entries with user email and wallet name via JOINs
        # This replaces 3 separate queries with 1 JOIN operation
        rut_with_metadata = {}
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
                sa.column("email"),  # from users table via LEFT JOIN
                sa.column("name").label("wallet_name"),  # from wallets table via LEFT JOIN
            )
            .select_from(
                sa.table("resource_tracker_service_runs")
                .join(
                    sa.table("users"),
                    sa.column("resource_tracker_service_runs.user_id") == sa.column("users.id"),
                    isouter=True,
                )
                .join(
                    sa.table("wallets"),
                    sa.column("resource_tracker_service_runs.wallet_id") == sa.column("wallets.wallet_id"),
                    isouter=True,
                )
            )
            .where(
                sa.and_(
                    sa.column("service_type") == "DYNAMIC_SERVICE",
                    sa.tuple_(sa.column("user_id"), sa.column("project_id"), sa.column("node_id")).in_(
                        [(pid, str(nid)) for uid, pid, nid in services]
                    ),
                )
            )
        )
        for row in result.fetchall():
            key = (str(row.project_id), str(row.node_id))
            rut_with_metadata[key] = {
                "rut": ResourceTrackerServiceRun(
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
                ),
                "email": str(row.email) if row.email else None,
                "wallet_name": str(row.wallet_name) if row.wallet_name else None,
            }

        # Fetch product USD rates in a single query for all products
        unique_products = {rut_with_metadata[key]["rut"].product_name for key in rut_with_metadata}
        product_usd: dict[str, float | None] = {}
        if unique_products:
            result = await conn.execute(
                sa.select(
                    sa.column("product_name"),
                    sa.column("usd_per_credit"),
                )
                .select_from(sa.table("products_prices"))
                .where(sa.column("product_name").in_(unique_products))
                .distinct(sa.column("product_name"))
                .order_by(sa.column("product_name"), sa.column("valid_from").desc())
            )
            seen_products = set()
            for row in result.fetchall():
                product_name = str(row.product_name)
                if product_name not in seen_products:
                    seen_products.add(product_name)
                    if row.usd_per_credit is not None:
                        value = float(row.usd_per_credit)
                        product_usd[product_name] = value if value > 0 else None
                    else:
                        product_usd[product_name] = None

    # Build final mapping
    info: dict[tuple[str, str], DynamicServiceExtraInfo] = {}
    for _, pid, nid in services:
        key = (pid, nid)
        metadata = rut_with_metadata.get(key)
        if metadata:
            rut = metadata["rut"]
            info[key] = DynamicServiceExtraInfo(
                email=metadata["email"],
                wallet_id=rut.wallet_id,
                wallet_name=metadata["wallet_name"],
                tracker_run=rut,
                usd_per_credit=product_usd.get(rut.product_name),
            )
        else:
            # Service not found in RUT; still include it with minimal info
            info[key] = DynamicServiceExtraInfo()
    return info


@cached()
async def get_product_usd_per_credit(
    engine: AsyncEngine,
    product_name: str,
) -> float | None:
    """Returns the latest usd_per_credit for the product, or None if not found."""
    async with engine.connect() as conn:
        result = await conn.execute(
            sa.select(sa.column("usd_per_credit"))
            .select_from(sa.table("products_prices"))
            .where(sa.column("product_name") == product_name)
            .order_by(sa.column("valid_from").desc())
            .limit(1)
        )
        row = result.fetchone()
        if row and row.usd_per_credit is not None:
            return float(row.usd_per_credit)
        return None
