import re
from typing import Any, Dict, Optional, TypedDict, Union
from uuid import UUID, uuid3

from models_library.basic_regex import UUID_RE
from models_library.projects import ProjectID

from .version_control_models import CommitID

# TODO: move this to modelslib?


def compose_wcopy_project_id(
    repo_project_uuid: Union[ProjectID, str], commit_id: CommitID
) -> UUID:
    """Produces a unique identifier for a working copy of a given repo_project_uuid@commit_id"""
    if isinstance(repo_project_uuid, str):
        repo_project_uuid = UUID(repo_project_uuid)
    return uuid3(repo_project_uuid, f"{commit_id}")


def compose_wcopy_project_tag_name(wcopy_project_id: ProjectID) -> str:
    return f"project:{wcopy_project_id}"


def parse_wcopy_project_tag_name(name: str) -> Optional[ProjectID]:
    if m := re.match(rf"^project:(?P<wcopy_project_id>{UUID_RE})$", name):
        data = m.groupdict()
        return ProjectID(data["wcopy_project_id"])
    return None
