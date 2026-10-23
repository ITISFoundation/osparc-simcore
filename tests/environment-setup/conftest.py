# pylint: disable=unused-argument
# pylint: disable=bare-except
# pylint: disable=redefined-outer-name

import json
import re
import sys
from pathlib import Path

import pytest

## current directory
current_dir = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent

pytest_plugins = [
    "pytest_simcore.repository_paths",
    "pytest_simcore.pytest_global_environs",
]


@pytest.fixture(scope="session")
def renovate_constraints(osparc_simcore_root_dir: Path) -> dict[str, str]:
    """Versions of the tools Renovate installs (`constraints` in .renovaterc.jsonc)"""
    text = (osparc_simcore_root_dir / ".renovaterc.jsonc").read_text()
    # only whole-line comments are stripped: "//" also occurs inside URL strings
    config = json.loads(re.sub(r"^\s*//.*$", "", text, flags=re.MULTILINE))
    return config["constraints"]
