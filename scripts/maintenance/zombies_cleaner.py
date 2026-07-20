#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "ansible>=10.7.0",
#   "asyncssh>=2.14",
#   "boto3>=1.34",
#   "psycopg[binary]>=3.2",
#   "pydantic>=2.9",
#   "python-dotenv>=1.0",
#   "rich>=13",
#   "simcore-common-library",
#   "simcore-postgres-database",
#   "sqlalchemy>=2",
#   "typer>=0.12",
# ]
#
# [tool.uv.sources]
# simcore-common-library = { path = "../../packages/common-library", editable = true }
# simcore-postgres-database = { path = "../../packages/postgres-database", editable = true }
# ///

from __future__ import annotations

import asyncio
import contextlib
import csv
import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Annotated
from urllib.parse import quote
from uuid import UUID

import asyncssh
import boto3
import sqlalchemy as sa
import typer
from ansible.inventory.manager import InventoryManager
from ansible.parsing.dataloader import DataLoader
from botocore.config import Config
from dotenv import dotenv_values
from pydantic import AnyHttpUrl, BaseModel, ByteSize, ConfigDict, SecretStr
from rich.console import Console
from rich.progress import BarColumn, MofNCompleteColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from simcore_postgres_database.models.comp_pipeline import comp_pipeline
from simcore_postgres_database.models.projects import projects
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

app = typer.Typer(help="Inspect and clean orphan comp_pipeline entries and their S3 objects.")
console = Console()


class PipelineRow(BaseModel):
    model_config = ConfigDict(frozen=True)

    project_id: UUID


class PrefixReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    project_id: UUID
    prefix: str
    exists: bool
    object_count: int
    total_size: ByteSize


_COMP_PIPELINE_ORPHAN = "comp_pipeline_orphan"
_STORAGE_ORPHAN = "storage_orphan"


class BucketOrphanReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    project_id: UUID
    classification: str
    object_count: int
    total_size: ByteSize


class DbConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    host: str
    port: int
    external_host: str
    external_port: int
    user: str
    password: SecretStr
    dbname: str


class BastionHost(BaseModel):
    model_config = ConfigDict(frozen=True)

    ip: str
    user_name: str


class S3Config(BaseModel):
    model_config = ConfigDict(frozen=True)

    endpoint_url: AnyHttpUrl | None
    region: str
    bucket: str
    access_key: str
    secret_key: SecretStr
    prefix_template: str


def _load_repo_config(deploy_config: Path) -> dict[str, str | None]:
    repo_config = deploy_config / "repo.config"
    if not repo_config.exists():
        console.print(
            f"[red]{repo_config} does not exist! Please point --deploy-config to a valid deployment directory[/red]"
        )
        raise typer.Exit(1)

    environment = dotenv_values(repo_config)
    if not environment:
        console.print(f"[red]{repo_config} is empty or could not be parsed[/red]")
        raise typer.Exit(1)
    return environment


def _db_config_from_env(environment: dict[str, str | None]) -> DbConfig:
    # NOTE: connect the same way autoscaled-monitor does: POSTGRES_HOST/PORT are only reachable
    # from inside the deployment's network, so they must be tunnelled through the bastion host
    # when one is configured. Some deployments have no bastion at all, in which case we connect
    # directly using POSTGRES_EXTERNAL_HOST/PORT (falling back to POSTGRES_HOST/PORT).
    host = environment.get("POSTGRES_HOST")
    port = environment.get("POSTGRES_PORT")
    external_host = environment.get("POSTGRES_EXTERNAL_HOST") or host
    external_port = environment.get("POSTGRES_EXTERNAL_PORT") or port
    user = environment.get("POSTGRES_USER")
    password = environment.get("POSTGRES_PASSWORD")
    dbname = environment.get("POSTGRES_DB")
    if not all([host, port, external_host, external_port, user, password, dbname]):
        console.print("[red]repo.config is missing POSTGRES_HOST/PORT/USER/PASSWORD/DB[/red]")
        raise typer.Exit(1)
    assert host  # nosec
    assert port  # nosec
    assert external_host  # nosec
    assert external_port  # nosec
    assert user  # nosec
    assert password  # nosec
    assert dbname  # nosec
    return DbConfig(
        host=host,
        port=int(port),
        external_host=external_host,
        external_port=int(external_port),
        user=user,
        password=password,
        dbname=dbname,
    )


def _parse_inventory(deploy_config: Path) -> BastionHost | None:
    # NOTE: mirrors autoscaled-monitor's main.py::_parse_inventory, but the bastion is optional:
    # some deployments have no bastion at all and are reachable directly.
    inventory_path = deploy_config / "ansible" / "inventory.ini"
    if not inventory_path.exists():
        console.print(f"[dim]No {inventory_path}, connecting to the database directly (no bastion)[/dim]")
        return None

    loader = DataLoader()
    inventory = InventoryManager(loader=loader, sources=[f"{inventory_path}"])
    try:
        return BastionHost(
            ip=inventory.groups["CAULDRON_UNIX"].get_vars()["bastion_ip"],
            user_name=inventory.groups["CAULDRON_UNIX"].get_vars()["bastion_user"],
        )
    except KeyError:
        console.print(f"[dim]No bastion_ip/bastion_user in {inventory_path}, connecting to the database directly[/dim]")
        return None


_EXCLUDED_SSH_KEY_MARKERS = ("dask", "license", "pkcs8")


def _find_ssh_key(deploy_config: Path) -> Path:
    # NOTE: mirrors autoscaled-monitor's main.py ssh key discovery. Only needed when a bastion
    # was found by _parse_inventory.
    for file_path in sorted(deploy_config.glob("**/*.pem")):
        if any(marker in file_path.name for marker in _EXCLUDED_SSH_KEY_MARKERS):
            continue
        return file_path
    console.print(
        f"[red]Could not find an SSH key (*.pem) in {deploy_config}! Please run OPS code to generate it[/red]"
    )
    raise typer.Exit(1)


def _s3_config_from_env(environment: dict[str, str | None], prefix_template: str) -> S3Config:
    endpoint = environment.get("S3_ENDPOINT")
    region = environment.get("S3_REGION")
    bucket = environment.get("S3_BUCKET_NAME") or environment.get("S3_BUCKET")
    access_key = environment.get("S3_ACCESS_KEY")
    secret_key = environment.get("S3_SECRET_KEY")
    if not all([region, bucket, access_key, secret_key]):
        console.print("[red]repo.config is missing one of S3_REGION/S3_BUCKET(_NAME)/S3_ACCESS_KEY/S3_SECRET_KEY[/red]")
        raise typer.Exit(1)
    return S3Config(
        endpoint_url=endpoint,
        region=region,
        bucket=bucket,
        access_key=access_key,
        secret_key=secret_key,
        prefix_template=prefix_template,
    )


def render_prefix(template: str, project_id: UUID) -> str:
    prefix = template.format(project_id=project_id).lstrip("/")
    return prefix if prefix.endswith("/") else f"{prefix}/"


@contextlib.asynccontextmanager
async def db_engine(
    cfg: DbConfig, bastion: BastionHost | None, ssh_key_path: Path | None
) -> AsyncIterator[AsyncEngine]:
    # NOTE: mirrors autoscaled-monitor's db.py::db_engine: tunnels POSTGRES_HOST/PORT through the
    # bastion host via an asyncssh port-forward when one is configured, otherwise connects
    # directly using POSTGRES_EXTERNAL_HOST/PORT.
    if bastion is None:
        console.print(f"[dim]Connecting directly to {cfg.external_host}:{cfg.external_port}...[/dim]")
        dsn = (
            f"postgresql+psycopg://{quote(cfg.user, safe='')}:{quote(cfg.password.get_secret_value(), safe='')}"
            f"@{cfg.external_host}:{cfg.external_port}/{cfg.dbname}"
        )
        engine = create_async_engine(dsn)
        try:
            yield engine
        finally:
            await engine.dispose()
        return

    assert ssh_key_path is not None  # nosec
    console.print(f"[dim]Opening SSH tunnel to {cfg.host}:{cfg.port} via bastion {bastion.ip}...[/dim]")
    async with asyncssh.connect(
        bastion.ip,
        port=22,
        username=bastion.user_name,
        client_keys=[str(ssh_key_path)],
        known_hosts=None,
    ) as ssh_conn:
        listener = await ssh_conn.forward_local_port("127.0.0.1", 0, cfg.host, cfg.port)
        try:
            dsn = (
                f"postgresql+psycopg://{quote(cfg.user, safe='')}:{quote(cfg.password.get_secret_value(), safe='')}"
                f"@127.0.0.1:{listener.get_port()}/{cfg.dbname}"
            )
            engine = create_async_engine(dsn)
            try:
                yield engine
            finally:
                await engine.dispose()
        finally:
            listener.close()
            await listener.wait_closed()


def _orphan_pipelines_query(limit: int | None) -> sa.Select:
    # NOTE: comp_pipeline's primary key IS project_id (there is no separate "id" column)
    # NOT EXISTS is preferred over LEFT JOIN ... IS NULL for anti-join patterns
    query = (
        sa.select(comp_pipeline.c.project_id)
        .where(~sa.exists(sa.select(sa.literal(1)).where(projects.c.uuid == comp_pipeline.c.project_id)))
        .order_by(comp_pipeline.c.project_id)
    )
    if limit is not None:
        query = query.limit(limit)
    return query


async def count_total_pipelines(engine: AsyncEngine) -> int:
    query = sa.select(sa.func.count()).select_from(comp_pipeline)
    async with engine.connect() as conn:
        result = await conn.execute(query)
        return result.scalar_one()


def _make_progress() -> Progress:
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console,
    )


def s3_client(cfg: S3Config):
    return boto3.client(
        "s3",
        endpoint_url=str(cfg.endpoint_url) if cfg.endpoint_url else None,
        region_name=cfg.region,
        aws_access_key_id=cfg.access_key,
        aws_secret_access_key=cfg.secret_key.get_secret_value(),
        config=Config(signature_version="s3v4"),
    )


async def fetch_orphan_pipelines(engine: AsyncEngine, limit: int | None) -> list[PipelineRow]:
    async with engine.connect() as conn:
        result = await conn.execute(_orphan_pipelines_query(limit))
        rows = result.mappings().all()
    return [PipelineRow(project_id=r["project_id"]) for r in rows]


def list_top_level_project_ids(client, bucket: str) -> list[UUID]:
    # NOTE: only consider first-level "folders" shaped like a project_id UUID, i.e. entries of
    # the form {project_id}/{node_id}/... . Anything else (e.g. "api/") is ignored.
    paginator = client.get_paginator("list_objects_v2")
    project_ids: list[UUID] = []
    for page in paginator.paginate(Bucket=bucket, Delimiter="/"):
        for common_prefix in page.get("CommonPrefixes", []):
            candidate = common_prefix.get("Prefix", "").rstrip("/")
            try:
                project_ids.append(UUID(candidate))
            except ValueError:
                continue
    return project_ids


async def classify_bucket_projects(engine: AsyncEngine, project_ids: list[UUID]) -> dict[UUID, str]:
    """Returns {project_id: classification} for S3 top-level ids that have no matching row in
    `projects`. `comp_pipeline_orphan` also has a matching orphan row in `comp_pipeline`;
    `storage_orphan` has no trace in the DB at all (just leftover S3 data).
    """
    if not project_ids:
        return {}
    str_ids = [str(p) for p in project_ids]
    async with engine.connect() as conn:
        existing_projects = await conn.execute(sa.select(projects.c.uuid).where(projects.c.uuid.in_(str_ids)))
        existing_project_ids = {str(u) for u in existing_projects.scalars().all()}

        existing_comp_pipelines = await conn.execute(
            sa.select(comp_pipeline.c.project_id).where(comp_pipeline.c.project_id.in_(str_ids))
        )
        comp_pipeline_ids = {str(u) for u in existing_comp_pipelines.scalars().all()}

    classification: dict[UUID, str] = {}
    for project_id in project_ids:
        key = str(project_id)
        if key in existing_project_ids:
            continue
        classification[project_id] = _COMP_PIPELINE_ORPHAN if key in comp_pipeline_ids else _STORAGE_ORPHAN
    return classification


def inspect_prefix(client, bucket: str, prefix: str, project_id: UUID) -> PrefixReport:
    paginator = client.get_paginator("list_objects_v2")
    object_count = 0
    total_size = 0
    exists = False
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            exists = True
            object_count += 1
            total_size += int(obj.get("Size", 0))
    return PrefixReport(
        project_id=project_id,
        prefix=prefix,
        exists=exists,
        object_count=object_count,
        total_size=total_size,
    )


def inspect_all(rows: list[PipelineRow], s3cfg: S3Config) -> list[PrefixReport]:
    client = s3_client(s3cfg)
    reports: list[PrefixReport] = []
    with _make_progress() as progress:
        task_id = progress.add_task("Inspecting S3 prefixes...", total=len(rows))
        for row in rows:
            prefix = render_prefix(s3cfg.prefix_template, row.project_id)
            reports.append(inspect_prefix(client, s3cfg.bucket, prefix, row.project_id))
            progress.advance(task_id)
    return reports


def write_report(path: str, reports: list[PrefixReport]) -> None:
    with Path(path).open("w", newline="") as fp:
        writer = csv.writer(fp)
        writer.writerow(["project_id", "prefix", "exists", "object_count", "total_size_bytes"])
        for r in reports:
            writer.writerow([r.project_id, r.prefix, r.exists, r.object_count, int(r.total_size)])


def write_bucket_orphans_report(path: str, reports: list[BucketOrphanReport]) -> None:
    with Path(path).open("w", newline="") as fp:
        writer = csv.writer(fp)
        writer.writerow(["project_id", "classification", "object_count", "total_size_bytes"])
        for r in sorted(reports, key=lambda r: (r.classification, str(r.project_id))):
            writer.writerow([r.project_id, r.classification, r.object_count, int(r.total_size)])


def delete_s3_prefix(client, bucket: str, prefix: str) -> tuple[int, int]:
    paginator = client.get_paginator("list_objects_v2")
    deleted_objects = 0
    deleted_bytes = 0
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        contents = page.get("Contents", [])
        if not contents:
            continue
        batch = [{"Key": obj["Key"]} for obj in contents]
        deleted_objects += len(batch)
        deleted_bytes += sum(int(obj.get("Size", 0)) for obj in contents)
        client.delete_objects(Bucket=bucket, Delete={"Objects": batch, "Quiet": True})
    return deleted_objects, deleted_bytes


async def delete_db_rows(engine: AsyncEngine, project_ids: list[UUID]) -> int:
    if not project_ids:
        return 0
    query = sa.delete(comp_pipeline).where(comp_pipeline.c.project_id.in_([str(p) for p in project_ids]))
    async with engine.begin() as conn:
        result = await conn.execute(query)
        return result.rowcount


def summarize(reports: list[PrefixReport]) -> dict:
    total_size = ByteSize(sum(int(r.total_size) for r in reports))
    return {
        "pipelines_found": len(reports),
        "prefixes_existing": sum(1 for r in reports if r.exists),
        "objects_found": sum(r.object_count for r in reports),
        "total_size_bytes": int(total_size),
        "total_size_human": total_size.human_readable(),
    }


@app.command()
def inspect(
    deploy_config: Annotated[
        Path,
        typer.Option(
            exists=True,
            file_okay=False,
            dir_okay=True,
            help="Path to the deployment configuration directory (must contain a repo.config file)",
        ),
    ],
    s3_prefix_template: str = typer.Option(
        "{project_id}/", help="Prefix template, e.g. storage/projects/{project_id}/"
    ),
    limit: int | None = typer.Option(None, help="Optional max number of orphan rows to inspect"),
    report_csv: str = typer.Option("comp_pipeline_cleanup_report.csv", help="CSV output path"),
):
    asyncio.run(_inspect_async(deploy_config, s3_prefix_template, limit, report_csv))


async def _inspect_async(deploy_config: Path, s3_prefix_template: str, limit: int | None, report_csv: str) -> None:
    deploy_config = deploy_config.expanduser()
    environment = _load_repo_config(deploy_config)
    dbcfg = _db_config_from_env(environment)
    s3cfg = _s3_config_from_env(environment, s3_prefix_template)
    bastion = _parse_inventory(deploy_config)
    ssh_key_path = _find_ssh_key(deploy_config) if bastion is not None else None

    async with db_engine(dbcfg, bastion, ssh_key_path) as engine:
        total_pipelines = await count_total_pipelines(engine)
        rows = await fetch_orphan_pipelines(engine, limit)
        console.print(f"[bold]Total comp_pipeline entries in DB:[/bold] {total_pipelines}")
        console.print(f"[bold]Orphan entries to inspect:[/bold] {len(rows)}")

    reports = inspect_all(rows, s3cfg)
    write_report(report_csv, reports)
    summary = summarize(reports)

    console.print(
        f"[bold]Total S3 size for orphan prefixes:[/bold] {summary['total_size_human']} "
        f"({summary['objects_found']} objects)"
    )
    typer.echo(json.dumps(summary, indent=2))
    typer.echo(f"Report written to {report_csv}")


@app.command()
def cleanup(
    deploy_config: Annotated[
        Path,
        typer.Option(
            exists=True,
            file_okay=False,
            dir_okay=True,
            help="Path to the deployment configuration directory (must contain a repo.config file)",
        ),
    ],
    s3_prefix_template: str = typer.Option(..., help="Prefix template"),
    limit: int | None = typer.Option(None, help="Optional max number of orphan rows to clean"),
    yes: bool = typer.Option(False, "--yes", help="Skip confirmation prompt"),  # noqa: FBT001, FBT003
):
    asyncio.run(_cleanup_async(deploy_config, s3_prefix_template, limit, yes=yes))


async def _cleanup_async(deploy_config: Path, s3_prefix_template: str, limit: int | None, *, yes: bool) -> None:
    deploy_config = deploy_config.expanduser()
    environment = _load_repo_config(deploy_config)
    dbcfg = _db_config_from_env(environment)
    s3cfg = _s3_config_from_env(environment, s3_prefix_template)
    client = s3_client(s3cfg)
    bastion = _parse_inventory(deploy_config)
    ssh_key_path = _find_ssh_key(deploy_config) if bastion is not None else None

    async with db_engine(dbcfg, bastion, ssh_key_path) as engine:
        total_pipelines = await count_total_pipelines(engine)
        rows = await fetch_orphan_pipelines(engine, limit)
        console.print(f"[bold]Total comp_pipeline entries in DB:[/bold] {total_pipelines}")
        console.print(f"[bold]Orphan entries to clean:[/bold] {len(rows)}")

        reports = inspect_all(rows, s3cfg)
        summary = summarize(reports)

        console.print(
            f"[bold]Total S3 size for orphan prefixes:[/bold] {summary['total_size_human']} "
            f"({summary['objects_found']} objects)"
        )
        typer.echo(json.dumps(summary, indent=2))
        if not yes:
            confirmed = typer.confirm(
                "Delete the listed S3 objects and then remove the matching comp_pipeline rows?", abort=False
            )
            if not confirmed:
                typer.echo("Aborted.")
                raise typer.Exit(code=0)

        deleted_objects = 0
        deleted_bytes = 0
        project_ids: list[UUID] = []
        with _make_progress() as progress:
            task_id = progress.add_task("Deleting orphan S3 prefixes...", total=len(reports))
            for report in reports:
                if report.exists:
                    obj_count, size_count = delete_s3_prefix(client, s3cfg.bucket, report.prefix)
                    deleted_objects += obj_count
                    deleted_bytes += size_count
                project_ids.append(report.project_id)
                progress.advance(task_id)

        deleted_rows = await delete_db_rows(engine, project_ids)

    typer.echo(
        json.dumps(
            {
                "deleted_objects": deleted_objects,
                "deleted_size_bytes": deleted_bytes,
                "deleted_size_human": ByteSize(deleted_bytes).human_readable(),
                "deleted_db_rows": deleted_rows,
            },
            indent=2,
        )
    )


@app.command()
def sql(
    limit: int | None = typer.Option(None, help="Optional SQL LIMIT to append"),
):
    query = _orphan_pipelines_query(limit)
    compiled = query.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True})
    typer.echo(f"{compiled};")


@app.command("scan-bucket")
def scan_bucket(
    deploy_config: Annotated[
        Path,
        typer.Option(
            exists=True,
            file_okay=False,
            dir_okay=True,
            help="Path to the deployment configuration directory (must contain a repo.config file)",
        ),
    ],
    report_csv: str = typer.Option("s3_bucket_orphans_report.csv", help="CSV output path"),
):
    """Scan the S3 bucket's top-level {project_id}/ prefixes and report the ones with no matching
    row in `projects`, classified as comp_pipeline_orphan (also orphaned in comp_pipeline) or
    storage_orphan (no DB trace at all).
    """
    asyncio.run(_scan_bucket_async(deploy_config, report_csv))


async def _scan_bucket_async(deploy_config: Path, report_csv: str) -> None:
    deploy_config = deploy_config.expanduser()
    environment = _load_repo_config(deploy_config)
    dbcfg = _db_config_from_env(environment)
    s3cfg = _s3_config_from_env(environment, "{project_id}/")
    bastion = _parse_inventory(deploy_config)
    ssh_key_path = _find_ssh_key(deploy_config) if bastion is not None else None

    client = s3_client(s3cfg)
    console.print("[bold]Listing top-level S3 prefixes...[/bold]")
    project_ids = list_top_level_project_ids(client, s3cfg.bucket)
    console.print(f"[bold]Candidate project prefixes found in S3:[/bold] {len(project_ids)}")

    async with db_engine(dbcfg, bastion, ssh_key_path) as engine:
        classification = await classify_bucket_projects(engine, project_ids)
    console.print(f"[bold]Orphaned prefixes (no matching project):[/bold] {len(classification)}")

    reports: list[BucketOrphanReport] = []
    with _make_progress() as progress:
        task_id = progress.add_task("Inspecting orphaned S3 prefixes...", total=len(classification))
        for project_id, kind in classification.items():
            prefix_report = inspect_prefix(client, s3cfg.bucket, f"{project_id}/", project_id)
            reports.append(
                BucketOrphanReport(
                    project_id=project_id,
                    classification=kind,
                    object_count=prefix_report.object_count,
                    total_size=prefix_report.total_size,
                )
            )
            progress.advance(task_id)

    write_bucket_orphans_report(report_csv, reports)

    comp_pipeline_orphans = [r for r in reports if r.classification == _COMP_PIPELINE_ORPHAN]
    storage_orphans = [r for r in reports if r.classification == _STORAGE_ORPHAN]
    summary = {
        "candidate_prefixes": len(project_ids),
        "orphaned_prefixes": len(reports),
        "comp_pipeline_orphans": len(comp_pipeline_orphans),
        "comp_pipeline_orphans_size_bytes": sum(int(r.total_size) for r in comp_pipeline_orphans),
        "storage_orphans": len(storage_orphans),
        "storage_orphans_size_bytes": sum(int(r.total_size) for r in storage_orphans),
    }
    typer.echo(json.dumps(summary, indent=2))
    typer.echo(f"Report written to {report_csv}")


if __name__ == "__main__":
    app()
