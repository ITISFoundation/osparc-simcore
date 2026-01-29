import logging
from pathlib import Path

from common_library.json_serialization import json_dumps
from jinja2 import Environment, FileSystemLoader, PackageLoader, select_autoescape

import notifications_library

_logger = logging.getLogger(__name__)


def create_render_environment_from_notifications_library(**kwargs) -> Environment:
    env = Environment(
        loader=PackageLoader(notifications_library.__name__, "templates"),
        autoescape=select_autoescape(["html", "xml"]),
        **kwargs,
    )
    env.globals["dumps"] = json_dumps
    return env


def create_render_environment_from_folder(top_dir: Path) -> Environment:
    assert top_dir.exists()  # nosec
    assert top_dir.is_dir()  # nosec
    env = Environment(
        loader=FileSystemLoader(top_dir),
        autoescape=select_autoescape(
            ["html", "xml"],
        ),
    )
    env.globals["dumps"] = json_dumps
    return env
