# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from datetime import datetime, timezone
from typing import Any, Dict

from models_library.projects import Project
from simcore_service_webserver.repos_models import Snapshot
from simcore_service_webserver.repos_snapshots import take_snapshot

ProjectDict = Dict[str, Any]


async def test_take_snapshot(user_project: ProjectDict):

    project, snapshot = await take_snapshot(
        parent=user_project, snapshot_label="some snapshot"
    )

    assert isinstance(project, dict)
    assert isinstance(snapshot, Snapshot)

    # project overrides ORM-only fields
    assert project["hidden"]
    assert not project["published"]

    # domain models
    parent = Project.parse_obj(user_project)

    # snapshot timestamp corresponds to the last change of the project
    def to_dt(timestamp):
        return datetime.fromisoformat(timestamp[:-1]).replace(tzinfo=timezone.utc)

    assert snapshot.created_at == to_dt(parent.last_change_date)
    assert to_dt(project["creationDate"]) == snapshot.created_at
