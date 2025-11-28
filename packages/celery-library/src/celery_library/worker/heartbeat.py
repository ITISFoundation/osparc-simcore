import tempfile
import time
from pathlib import Path
from typing import Final

HEARTBEAT_FILE: Final[Path] = Path(tempfile.gettempdir()) / "celery_heartbeat"

def update_heartbeat() -> None:
    tmp_file = HEARTBEAT_FILE.with_suffix(".tmp")
    tmp_file.write_text(f"{time.time()}")
    tmp_file.replace(HEARTBEAT_FILE)


def is_healthy(threshold_seconds: int = 10) -> bool:
    if not HEARTBEAT_FILE.exists():
        return False

    try:
        heartbeat = float(HEARTBEAT_FILE.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return False

    return (time.time() - heartbeat) <= threshold_seconds
