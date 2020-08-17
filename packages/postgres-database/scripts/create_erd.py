#
# ERD (Entity Relationship Diagram) is used to visualize these relationships
#
# Needs: pip install eralchemy

# pylint: disable=widlcard-import
# pylint: disable=wildcard-import-unused

from eralchemy import render_er

from simcore_postgres_database.models import * # registers all schemas in metadata
from simcore_postgres_database.models.base import metadata


filename = '../doc/img/postgres-database-models.svg'
render_er(metadata, filename)
