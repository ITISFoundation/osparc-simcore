import csv
import json
from pathlib import Path

import typer
from models_library.projects import ProjectAtDB
from pydantic import ConfigDict, Json, ValidationError, field_validator


class ProjectFromCsv(ProjectAtDB):
    # TODO: missing in ProjectAtDB

    access_rights: Json
    ui: Json
    classifiers: str  # FIXME: this is ARRAY[sa.STRING]
    dev: Json
    quality: Json

    hidden: bool

    model_config = ConfigDict(extra="forbid")

    # NOTE: validators introduced to parse CSV

    @field_validator("published", "hidden", mode="before", check_fields=False)
    @classmethod
    def empty_str_as_false(cls, v):
        # See booleans for >v1.0  https://pydantic-docs.helpmanual.io/usage/types/#booleans
        if isinstance(v, str) and v == "":
            return False
        return v

    @field_validator("workbench", mode="before", check_fields=False)
    @classmethod
    def jsonstr_to_dict(cls, v):
        if isinstance(v, str):
            return json.loads(v)
        return v


def validate_csv_exported_pg_project(
    csvpath: Path, verbose: int = typer.Option(0, "--verbose", "-v", count=True)
):
    """Validates a postgres (pg) projects table exported as a CSV file


    EXAMPLES
        $ for f in *.csv; do python validate-pg-projects.py -v $f >$f.log 2>&1 ; done

    TIP: CSV file can be obtained directly from Adminer website
    """
    typer.echo(f"Validating {csvpath} ...")

    failed = []
    index = -1
    with csvpath.open(encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        for index, row in enumerate(reader):
            pid = row.get("uuid", index + 1)

            try:
                model = ProjectFromCsv.model_validate(row)

                if verbose > 1:
                    typer.secho(f"{pid} OK", fg=typer.colors.GREEN)
                    if verbose > 2:
                        typer.echo(model.model_dump_json(indent=2))
            except ValidationError as err:
                failed.append(pid)
                typer.secho(
                    f"Invalid project {pid} (from {row['last_change_date']}", err=True
                )
                typer.secho(f" {err}", fg=typer.colors.RED, err=True)

    if failed:
        typer.secho(
            f"Found {len(failed)}/{index+1} invalid projects",
            fg=typer.colors.RED,
            err=True,
        )


if __name__ == "__main__":
    typer.run(validate_csv_exported_pg_project)
