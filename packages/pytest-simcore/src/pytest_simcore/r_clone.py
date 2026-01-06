import re
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def r_clone_version(osparc_simcore_root_dir: Path) -> str:
    install_rclone_bash = osparc_simcore_root_dir / "scripts" / "install_rclone.bash"
    assert install_rclone_bash.exists()

    match = re.search(r'R_CLONE_VERSION="([\d.]+)"', install_rclone_bash.read_text())
    assert match
    return match.group(1)
