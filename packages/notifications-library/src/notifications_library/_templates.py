import importlib.resources
import logging
from pathlib import Path

_logger = logging.getLogger(__name__)


_td = importlib.resources.files("notifications_library.templates")
_templates_dir = Path(f"{_td}")

#
# templates naming is formatted as "{event_name}.{provider}.{part}.{format}"
#


def get_email_templates(event_name: str) -> dict[str, Path]:
    return {p.name: p for p in _templates_dir.glob(f"{event_name}.email.*")}
