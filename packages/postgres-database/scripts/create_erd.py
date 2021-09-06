#
# ERD (Entity Relationship Diagram) is used to visualize these relationships
#
# Requires
#   - sudo apt install graphviz graphviz-dev
#   - pip install eralchemy
#
# TODO: create image with requirements
#
# pylint: disable=wildcard-import
# pylint: disable=unused-wildcard-import
#
import sys
from pathlib import Path

from simcore_postgres_database.models import *  # registers all schemas in metadata
from simcore_postgres_database.models.base import metadata

CURRENT_DIR = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent


def create_with_sqlalchemy_schemadisplay(svg_path: Path):
    # SEE https://github.com/sqlalchemy/sqlalchemy/wiki/SchemaDisplay

    from sqlalchemy_schemadisplay import create_schema_graph

    # create the pydot graph object by autoloading all tables via a bound metadata object

    graph = create_schema_graph(
        metadata=metadata,
        show_datatypes=True,  # The image would get nasty big if we'd show the datatypes
        show_indexes=False,  # ditto for indexes
        rankdir="LR",  # From left to right (instead of top to bottom)
        concentrate=False,  # Don't try to join the relation lines together
    )
    graph.write_svg(str(svg_path))  # write out the file


def create_with_eralchemy(svg_path: Path):
    # SEE https://github.com/Alexis-benoist/eralchemy
    from eralchemy import render_er

    render_er(metadata, str(svg_path))


if __name__ == "__main__":

    output_dir = (CURRENT_DIR / "../doc/img").resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    # FIXME: sqlalchemy_schemadisplay failes with json columns
    # create_with_sqlalchemy_schemadisplay( output_dir / "postgres-database-models.svg")

    create_with_eralchemy(output_dir / "postgres-database-models.svg")
