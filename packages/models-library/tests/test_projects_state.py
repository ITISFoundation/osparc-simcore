import pytest
from models_library.projects_state import (
    ProjectLocked,
    ProjectShareState,
    ProjectStatus,
)


def test_project_locked_with_missing_owner_raises():
    with pytest.raises(ValueError, match=r"1 validation error for ProjectLocked"):
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
    with pytest.raises(ValueError, match=r"1 validation error for ProjectLocked"):
        ProjectLocked.model_validate({"value": lock, "status": status})


@pytest.mark.parametrize(
    "status,locked,current_users,should_raise",
    [
        (ProjectStatus.CLOSED, False, [], False),
        (ProjectStatus.OPENING, False, [1, 2], False),
        (ProjectStatus.OPENED, False, [1], False),
        (ProjectStatus.CLONING, True, [1], False),
        (ProjectStatus.EXPORTING, True, [1], False),
        (ProjectStatus.MAINTAINING, True, [1], False),
        # Invalid: locked but no users
        (ProjectStatus.CLONING, True, [], True),
        # Invalid: closed but has users
        (ProjectStatus.CLOSED, False, [1], True),
        # Invalid: not closed but no users
        (ProjectStatus.OPENED, False, [], True),
    ],
)
def test_project_share_state_validations(status, locked, current_users, should_raise):
    data = {
        "status": status,
        "locked": locked,
        "current_users": current_users,
    }
    if should_raise:
        with pytest.raises(ValueError, match=r"If the project is "):
            ProjectShareState.model_validate(data)
    else:
        state = ProjectShareState.model_validate(data)
        assert state.status == status
        assert state.locked == locked
        assert state.current_users == current_users
