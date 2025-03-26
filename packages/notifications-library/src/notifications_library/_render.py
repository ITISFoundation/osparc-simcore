import logging
from pathlib import Path

import notifications_library
from jinja2 import Environment, FileSystemLoader, PackageLoader, select_autoescape

_logger = logging.getLogger(__name__)


def create_render_environment_from_notifications_library(**kwargs) -> Environment:
    return Environment(
        loader=PackageLoader(notifications_library.__name__, "templates"),
        autoescape=select_autoescape(["html", "xml"]),
        **kwargs
    )


def create_render_environment_from_folder(top_dir: Path) -> Environment:
    assert top_dir.exists()  # nosec
    assert top_dir.is_dir()  # nosec
    return Environment(
        loader=FileSystemLoader(top_dir),
        autoescape=select_autoescape(
            ["html", "xml"],
        ),
    )
