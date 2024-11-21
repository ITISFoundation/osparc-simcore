import argparse
import logging
import sys
from pathlib import Path

import yaml

_logger = logging.getLogger(__name__)


CURRENT_DIR = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent
SCHEMAS_DIR = CURRENT_DIR.parent


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        "Remove Definitions",
        description="prunes 'definitions' from json-schemas in 'source_file_name' and dumps it into 'target_file_name'",
    )
    parser.add_argument("source_file_name", type=str)
    parser.add_argument("target_file_name", type=str)
    args = parser.parse_args()

    file_source_path: Path = SCHEMAS_DIR / args.source_file_name
    file_target_path: Path = SCHEMAS_DIR / args.target_file_name

    try:
        data = yaml.safe_load(file_source_path.read_text())
        data.pop("definitions", None)
        with Path.open(file_target_path, "w") as file_stream:
            yaml.safe_dump(data, file_stream)
    except yaml.YAMLError:
        _logger.exception(
            "Ignoring error while load+pop+dump %s -> %s",
            file_source_path,
            file_target_path,
        )
