import re

from models_library.basic_regex import UUID_RE_BASE
from models_library.projects import ProjectID


def compose_workcopy_project_tag_name(workcopy_project_id: ProjectID) -> str:
    return f"project:{workcopy_project_id}"


def parse_workcopy_project_tag_name(name: str) -> ProjectID | None:
    if m := re.match(rf"^project:(?P<workcopy_project_id>{UUID_RE_BASE})$", name):
        data = m.groupdict()
        return ProjectID(data["workcopy_project_id"])
    return None
