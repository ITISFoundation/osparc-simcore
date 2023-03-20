""" Helpers, repository pattern, errors and data structures for models.projects

"""
from typing import TypedDict

from .models.projects import ProjectType, projects


# Structured dict with partial or complete project row data w/o any guarantees on which
# fields will be in place. Therefore, provide defaults on every get access.
class ProjectData(TypedDict):
    type: ProjectType
    published: bool


def can_guest_copy_project(prj_data: ProjectData) -> bool:
    """Returns True if a user with role GUEST can copy this template project"""

    assert "published" in projects.columns  # nosec
    assert "type" in projects.columns  # nosec

    return (
        prj_data.get("published", False)
        and prj_data.get("type", None) == ProjectType.TEMPLATE
    )
