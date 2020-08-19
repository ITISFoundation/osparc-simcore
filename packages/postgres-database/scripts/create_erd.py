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

from eralchemy import render_er

from simcore_postgres_database.models import *  # registers all schemas in metadata
from simcore_postgres_database.models.base import metadata

current_dir = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent


def main():
    output = (current_dir / "../doc/img/postgres-database-models.svg").resolve()
    render_er(metadata, str(output))


if __name__ == "__main__":
    main()
