import logging
from dataclasses import dataclass
from typing import TypedDict

from aiohttp import web
from simcore_postgres_database.models.projects import ProjectType, projects
from yarl import URL

from ..utils_aiohttp import create_url_for_function

_logger = logging.getLogger(__name__)


# Expected inputs models
_GroupID = str


class _GroupAccessRightsDict(TypedDict):
    read: bool
    write: bool
    delete: bool


assert "uuid" in projects.columns  # nosec
assert "type" in projects.columns  # nosec
assert "access_rights" in projects.columns  # nosec
assert "published" in projects.columns  # nosec


class _ProjectSelectionDict(TypedDict):
    uuid: str
    type: ProjectType
    access_rights: dict[_GroupID, _GroupAccessRightsDict]
    published: bool


# Output models
@dataclass
class StudyPermalinkInfo:
    url: URL
    is_public: bool


# Errors
class PermalinkNotAllowedError(RuntimeError):
    ...


def create_permalink_for_study_or_none(
    request: web.Request, project_data: _ProjectSelectionDict
) -> StudyPermalinkInfo | None:
    try:
        return create_permalink_for_study(request, project_data)
    except (PermalinkNotAllowedError, KeyError) as err:
        _logger.debug(err)
        return None


def create_permalink_for_study(
    request: web.Request, project_data: _ProjectSelectionDict
) -> StudyPermalinkInfo:
    """
    raises PermalinkNotAllowed
    """

    # get

    project_uuid: str = project_data["uuid"]
    project_type: ProjectType = project_data["type"]
    project_access_rights: dict[_GroupID, _GroupAccessRightsDict] = project_data[
        "access_rights"
    ]

    project_is_public: bool = project_data["published"]

    # checks
    if project_type != ProjectType.TEMPLATE:
        raise PermalinkNotAllowedError(
            "Can only create permalink from a template project. "
            f"Got {project_uuid=} with {project_type=}"
        )

    if not project_access_rights.get("1", {}).get("read", False):
        raise PermalinkNotAllowedError(
            "Cannot create permalink if not shared with everyone. "
            f"Got {project_uuid=} with {project_access_rights=}"
        )

    # create
    url_for = create_url_for_function(request)

    permalink: str = url_for(
        route_name="get_redirection_to_study_page", id=f"{project_uuid}"
    )

    return StudyPermalinkInfo(
        url=URL(permalink),
        is_public=project_is_public,
    )
