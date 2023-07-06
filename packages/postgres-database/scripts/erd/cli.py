#
# ERD (Entity Relationship Diagram) is used to visualize these relationships
#
# - Uses sqlalchemy_schemadisplay which is maintained by sqlalchemy
# - DROPPED 'eralchemy' since it fails with latest version and is not maintained anymore
#
# SEE https://github.com/sqlalchemy/sqlalchemy/wiki/SchemaDisplay
# SEE https://github.com/Alexis-benoist/eralchemy

# pylint: disable=wildcard-import
# pylint: disable=unused-wildcard-import


import argparse
import importlib
import logging
from pathlib import Path
from typing import Any

import simcore_postgres_database.models
from simcore_postgres_database.models.base import metadata
from sqlalchemy_schemadisplay import create_schema_graph

models_folder = Path(simcore_postgres_database.models.__file__).parent
# imports all models to fill "metadata"
for p in models_folder.glob("*.py"):
    if not p.name.startswith("__"):
        importlib.import_module(
            f"simcore_postgres_database.models.{p.name.removesuffix('.py')}"
        )


def create_erd(image_path: Path, include_table_names: list[str] | None = None):
    """
    create the pydot graph object by autoloading all tables via a bound metadata object
    """

    kwargs: dict[str, Any] = {
        "show_datatypes": True,  # The image would get nasty big if we'd show the datatypes
        "show_indexes": False,  # ditto for indexes
        "rankdir": "LR",  # From left to right (instead of top to bottom)
        "concentrate": False,  # Don't try to join the relation lines together
    }

    if include_table_names:
        kwargs["tables"] = [metadata.tables[t] for t in include_table_names]
    else:
        kwargs["metadata"] = metadata

    graph = create_schema_graph(**kwargs)

    # pylint: disable=no-member
    graph.write_svg(f'{image_path.with_suffix(".svg")}')
    graph.write_png(f'{image_path.with_suffix(".png")}')
    return image_path


def main():
    parser = argparse.ArgumentParser(
        description="Creates file with an Entity Relationship Diagram (ERD) of simcore_postgres_database.models"
    )
    parser.add_argument(
        "--output",
        help="Path to erd image (.svg, .png)",
        default="postgres-database-erd-ignore.svg",
    )
    parser.add_argument(
        "--include",
        nargs="*",
        help="List of table names to include in the ERD e.g. '--include projects projects_nodes'",
        default=None,
    )
    args = parser.parse_args()

    created_path = create_erd(
        image_path=Path(args.output),
        include_table_names=args.include,
    )
    logging.info("Created %s", f"{created_path=}")


if __name__ == "__main__":
    main()
