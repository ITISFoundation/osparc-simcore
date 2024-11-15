import pytest
from models_library.projects_state import ProjectLocked, ProjectStatus


def test_project_locked_with_missing_owner_raises():
    with pytest.raises(ValueError):
        ProjectLocked(value=True, status=ProjectStatus.OPENED)
    ProjectLocked.model_validate({"value": False, "status": ProjectStatus.OPENED})


def test_project_locked_with_missing_owner_ok_during_maintaining():
    ProjectLocked.model_validate({"value": True, "status": ProjectStatus.MAINTAINING})


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
        ProjectLocked.model_validate({"value": lock, "status": status})
