#
# ERD (Entity Relationship Diagram) is used to visualize these relationships
#
# Needs: pip install eralchemy

from simcore_postgres_database.models.base import metadata
from eralchemy import render_er

filename = '../doc/img/postgres-database-models.svg'
render_er(metadata, filename)

