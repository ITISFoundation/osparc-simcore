#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
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

import csv
import json
from pathlib import Path
from typing import Annotated
from urllib.parse import quote
from uuid import UUID

import boto3
import sqlalchemy as sa
import typer
from botocore.config import Config
from dotenv import dotenv_values
from pydantic import AnyHttpUrl, BaseModel, ByteSize, ConfigDict, PostgresDsn, SecretStr
from rich.console import Console
from rich.progress import BarColumn, MofNCompleteColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from simcore_postgres_database.models.comp_pipeline import comp_pipeline
from simcore_postgres_database.models.projects import projects
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine import Engine

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


class DbConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    dsn: PostgresDsn


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
    host = environment.get("POSTGRES_EXTERNAL_HOST") or environment.get("POSTGRES_HOST")
    port = environment.get("POSTGRES_EXTERNAL_PORT") or environment.get("POSTGRES_PORT")
    user = environment.get("POSTGRES_USER")
    password = environment.get("POSTGRES_PASSWORD")
    dbname = environment.get("POSTGRES_DB")
    if not all([host, port, user, password, dbname]):
        console.print(
            "[red]repo.config is missing POSTGRES_(EXTERNAL_HOST|HOST)/(EXTERNAL_PORT|PORT)/USER/PASSWORD/DB[/red]"
        )
        raise typer.Exit(1)
    assert host  # nosec
    assert port  # nosec
    assert user  # nosec
    assert password  # nosec
    assert dbname  # nosec
    dsn = f"postgresql://{quote(user, safe='')}:{quote(password, safe='')}@{host}:{port}/{dbname}"
    return DbConfig(dsn=dsn)


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


def create_db_engine(cfg: DbConfig) -> Engine:
    # NOTE: force the psycopg (v3) driver regardless of the scheme provided in the DSN
    url = sa.engine.make_url(str(cfg.dsn)).set(drivername="postgresql+psycopg")
    return sa.create_engine(url)


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


def count_total_pipelines(engine: Engine) -> int:
    query = sa.select(sa.func.count()).select_from(comp_pipeline)
    with engine.connect() as conn:
        return conn.execute(query).scalar_one()


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


def fetch_orphan_pipelines(engine: Engine, limit: int | None) -> list[PipelineRow]:
    with engine.connect() as conn:
        rows = conn.execute(_orphan_pipelines_query(limit)).mappings().all()
    return [PipelineRow(project_id=r["project_id"]) for r in rows]


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


def delete_db_rows(engine: Engine, project_ids: list[UUID]) -> int:
    if not project_ids:
        return 0
    query = sa.delete(comp_pipeline).where(comp_pipeline.c.project_id.in_([str(p) for p in project_ids]))
    with engine.begin() as conn:
        result = conn.execute(query)
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
    environment = _load_repo_config(deploy_config.expanduser())
    dbcfg = _db_config_from_env(environment)
    s3cfg = _s3_config_from_env(environment, s3_prefix_template)

    engine = create_db_engine(dbcfg)

    total_pipelines = count_total_pipelines(engine)
    rows = fetch_orphan_pipelines(engine, limit)
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
    environment = _load_repo_config(deploy_config.expanduser())
    dbcfg = _db_config_from_env(environment)
    s3cfg = _s3_config_from_env(environment, s3_prefix_template)
    client = s3_client(s3cfg)
    engine = create_db_engine(dbcfg)

    total_pipelines = count_total_pipelines(engine)
    rows = fetch_orphan_pipelines(engine, limit)
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

    deleted_rows = delete_db_rows(engine, project_ids)

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


if __name__ == "__main__":
    app()
