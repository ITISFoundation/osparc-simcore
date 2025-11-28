import time
from pathlib import Path

HEARTBEAT_FILE = Path("/tmp/celery_heartbeat")  # noqa: S108


def write_last_heartbeat() -> None:
    tmp_file = HEARTBEAT_FILE.with_suffix(".tmp")
    with tmp_file.open("w") as f:
        f.write(f"{time.time()}")
    tmp_file.replace(HEARTBEAT_FILE)


def is_heartbeat_fresh(threshold_seconds: int = 10) -> bool:
    if not HEARTBEAT_FILE.exists():
        return False

    try:
        heartbeat = float(HEARTBEAT_FILE.read_text(encoding="utf-8").strip())
    except (PermissionError, OSError, ValueError):
        return False

    return (time.time() - heartbeat) <= threshold_seconds
