# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import sys
from pathlib import Path

pytest_plugins = [
    "service_integration.pytest_plugin.folder_structure",
    "service_integration.pytest_plugin.validation_data",
    "service_integration.pytest_plugin.docker_integration",
]


current_dir = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent
