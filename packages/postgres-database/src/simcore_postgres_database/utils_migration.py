"""
    NOTE: this was decoupled from utils_cli.py in order to reduce requirements
"""
import sys
from pathlib import Path
from typing import Final, Optional

from alembic import __version__ as __alembic_version__
from alembic.config import Config as AlembicConfig
from alembic.script.base import ScriptDirectory

_CURRENT_DIR = Path(
    sys.argv[0] if __name__ == "__main__" else __file__
).parent.resolve()

DEFAULT_INI: Final[Path] = _CURRENT_DIR / "alembic.ini"
MIGRATION_DIR: Final[Path] = _CURRENT_DIR / "migration"

RevisionID = str


def create_basic_config() -> AlembicConfig:
    config = AlembicConfig(file_=str(DEFAULT_INI))
    config.set_main_option("script_location", str(MIGRATION_DIR))
    return config


def get_current_head() -> RevisionID:
    """Return the current head revision.

    If the script directory has multiple heads
    due to branching, an error is raised;
    """
    config = create_basic_config()
    script: ScriptDirectory = ScriptDirectory.from_config(config)

    head: Optional[str] = script.get_current_head()
    if not head:
        raise RuntimeError(f"Cannot find head revision in {script}")

    return head


# nopycln: file
