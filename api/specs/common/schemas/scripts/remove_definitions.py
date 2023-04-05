import logging
import sys
from pathlib import Path

import yaml

log = logging.getLogger(__name__)


current_dir = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent
schemas_dir = current_dir.parent


if __name__ == "__main__":
    source_file_name = sys.argv[1]
    target_file_name = sys.argv[2]

    file_source_path = schemas_dir / source_file_name
    file_target_path = schemas_dir / target_file_name

    try:
        data = yaml.safe_load(file_source_path.read_text())
        data.pop("definitions", None)
        with open(file_target_path, "w") as file_stream:
            yaml.safe_dump(data, file_stream)
    except yaml.YAMLError as exc:
        log.error(
            "Ignoring error while load+pop+dump %s -> %s",
            file_source_path,
            file_target_path,
        )
