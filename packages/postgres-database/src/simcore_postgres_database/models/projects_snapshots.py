#
#  Models to define version control snapshots for projects
#

import sqlalchemy as sa

from .base import metadata
from .projects import projects

_snapshot_uuid = projects.columns["uuid"].copy()
_snapshot_uuid.primary_key = True
_snapshot_uuid.doc = (
    "UUID for this project snapshot (different from working copy)."
    "Note that this uuid might not be present in the projects table."
)

projects_snapshots = sa.Table(
    "projects_snapshots",
    metadata,
    _snapshot_uuid,
    projects.columns["workbench"].copy(),
    projects.columns["ui"].copy(),
)
