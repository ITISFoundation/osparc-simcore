#
# ERD (Entity Relationship Diagram) is used to visualize these relationships
#
# - Using sqlalchemy_schemadisplay which is maintained by sqlalchemy
# - Already tried 'eralchemy' but fails with latest version and not maintained anymore
#
# SEE https://github.com/sqlalchemy/sqlalchemy/wiki/SchemaDisplay
# SEE https://github.com/Alexis-benoist/eralchemy

# pylint: disable=wildcard-import
# pylint: disable=unused-wildcard-import

from pathlib import Path
from typing import Any, Optional

from simcore_postgres_database.models import *  # registers all schemas in metadata
from simcore_postgres_database.models.base import metadata
from sqlalchemy_schemadisplay import create_schema_graph


def create_erd(image_path: Path, tables: Optional[list[str]] = None):
    """
    create the pydot graph object by autoloading all tables via a bound metadata object
    """

    kwargs: dict[str, Any] = dict(
        show_datatypes=True,  # The image would get nasty big if we'd show the datatypes
        show_indexes=False,  # ditto for indexes
        rankdir="LR",  # From left to right (instead of top to bottom)
        concentrate=False,  # Don't try to join the relation lines together
    )

    if tables:
        kwargs["tables"] = [metadata.tables[t] for t in tables]
    else:
        kwargs["metadata"] = metadata

    graph = create_schema_graph(kwargs)
    # pylint: disable=no-member
    graph.write_svg(f'{image_path.with_suffix(".svg")}')
    graph.write_png(f'{image_path.with_suffix(".png")}')


if __name__ == "__main__":
    path = Path("postgres-database-erd-ignore.svg")
    create_erd(path)
    print("Created", path)
