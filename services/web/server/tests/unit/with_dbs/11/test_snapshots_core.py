# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from typing import Any, Dict

from models_library.projects import Project
from simcore_service_webserver.snapshots_core import take_snapshot
from simcore_service_webserver.snapshots_models import Snapshot

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
    child = Project.parse_obj(project)

    # snapshot timestamp corresponds to the last change of the project
    assert snapshot.created_at == parent.last_change_date
    assert child.creation_date == snapshot.created_at
