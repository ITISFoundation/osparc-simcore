import pytest
from models_library.projects_state import ProjectLocked, ProjectStatus


@pytest.mark.parametrize(
    "lock, status",
    [
        (False, x)
        for x in ProjectStatus
        if x not in [ProjectStatus.CLOSED, ProjectStatus.OPENED]
    ]
    + [(True, ProjectStatus.CLOSED)],
)
def test_project_locked_with_allowed_values(lock: bool, status: ProjectStatus):
    with pytest.raises(ValueError):
        ProjectLocked.parse_obj({"value": lock, "status": status})
