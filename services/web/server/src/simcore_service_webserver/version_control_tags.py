import re
from typing import Optional

from models_library.basic_regex import UUID_RE
from models_library.projects import ProjectID


def compose_wcopy_project_tag_name(wcopy_project_id: ProjectID) -> str:
    return f"project:{wcopy_project_id}"


def parse_wcopy_project_tag_name(name: str) -> Optional[ProjectID]:
    if m := re.match(rf"^project:(?P<wcopy_project_id>{UUID_RE})$", name):
        data = m.groupdict()
        return ProjectID(data["wcopy_project_id"])
    return None
