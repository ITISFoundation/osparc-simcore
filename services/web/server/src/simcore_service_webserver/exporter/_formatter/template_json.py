from pathlib import Path

import aiofiles
from common_library.json_serialization import json_dumps

from ...projects.models import ProjectDict

FILE_NAME = "template.json"


def get_content(project_data: ProjectDict) -> str:
    data = {
        "uuid": project_data["uuid"],
        "name": project_data["name"],
        "description": project_data["description"],
    }
    return json_dumps(data)


async def write_template_json(target_dir: Path, project_data: ProjectDict) -> None:
    async with aiofiles.open(target_dir / FILE_NAME, "w") as f:
        await f.write(get_content(project_data))
