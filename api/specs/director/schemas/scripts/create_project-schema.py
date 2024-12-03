# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

import json
import sys
from pathlib import Path

import jsonref
from common_library.json_serialization import json_dumps
from models_library.projects import Project

CURRENT_DIR = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent


if __name__ == "__main__":
    with Path.open(
        CURRENT_DIR.parent / "common/schemas/project-v0.0.1-pydantic.json", "w"
    ) as f:
        schema = json_dumps(Project.model_json_schema())
        schema_without_ref = jsonref.loads(schema)

        json.dump(schema_without_ref, f, indent=2)
