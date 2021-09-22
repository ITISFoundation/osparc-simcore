import csv
import json
from pathlib import Path

import typer
from models_library.projects import ProjectAtDB
from pydantic import ValidationError, validator


class ProjectFromCsv(ProjectAtDB):
    @validator("published", "hidden", pre=True, check_fields=False)
    @classmethod
    def to_bool(cls, v):
        if isinstance(v, str) and v == "":
            return False
        return v

    @validator("workbench", pre=True, check_fields=False)
    @classmethod
    def json_to_dict(cls, v):
        if isinstance(v, str):
            return json.loads(v)
        return v


def validate_csv_exported_pg_project(
    csvpath: Path, verbose: int = typer.Option(0, "--verbose", "-v", count=True)
):
    """Validates rows of a postgres (pg) projects table exported as a CSV file

    TIP: CSV file can be obtained directly from Adminer website
    """
    typer.echo(f"Validating {csvpath} ...")

    failed = []
    with csvpath.open(encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        for index, row in enumerate(reader):
            pid = row.get("uuid", index + 1)

            try:
                model = ProjectFromCsv.parse_obj(row)

                if verbose:
                    typer.echo(f"{pid:*^100}")
                    if verbose > 1:
                        typer.echo(model.json(indent=2))
            except ValidationError as err:
                failed.append(pid)

                typer.secho(
                    f"Invalid project {pid}: {err}", fg=typer.colors.RED, err=True
                )

    if failed and verbose:
        typer.secho(
            f"Found {len(failed)} invalid projects",
            fg=typer.colors.RED,
            err=True,
        )


if __name__ == "__main__":
    typer.run(validate_csv_exported_pg_project)
