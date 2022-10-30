import logging
import sys
import tempfile
from pathlib import Path
from typing import Optional

import pytest

CURRENT_DIR = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent
TESTS_DIR = CURRENT_DIR / "tests"

logger = logging.getLogger(__name__)


def main(
    service_dir: Path, *, debug: bool = False, extra_args: Optional[list[str]] = None
) -> int:

    pytest_args = [
        # global cache options
        "--cache-clear",
        f"--override-ini=cache_dir={tempfile.gettempdir()}/.pytest_cache__service_integration",
        # tests
        f"{TESTS_DIR}",
        # custom options
        f"--service-under-test-dir={service_dir}",
    ]

    if debug:
        pytest_args += ["-vv", "--log-level=DEBUG", "--pdb"]

    if extra_args:
        pytest_args += extra_args

    logger.debug("Running 'pytest %s'", " ".join(pytest_args))
    exit_code = pytest.main(pytest_args)
    logger.debug("exit with code=%d", exit_code)
    return exit_code


if __name__ == "__main__":
    # Entrypoint for stand-alone 'service_integration/service' package
    sys.exit(
        main(
            service_dir=Path(sys.argv[1]),
            extra_args=sys.argv[2:],
        )
    )
