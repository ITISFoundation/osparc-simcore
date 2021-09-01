#
#  Models to define version control snapshots for projects
#

import sqlalchemy as sa

from .base import metadata
from .projects import projects

SNAPSHOT_COLUMNS = ("workbench", "ui")

_snapshot_uuid = projects.columns["uuid"].copy()
_snapshot_uuid.doc = (
    "UUID for this project snapshot (different from working copy)."
    "Note that this uuid might not be present in the projects table."
)

projects_snapshots = sa.Table(
    "projects_snapshots",
    metadata,
    _snapshot_uuid,
    *[projects.columns[name].copy() for name in SNAPSHOT_COLUMNS]
)
