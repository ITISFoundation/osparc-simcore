import logging
from functools import partial
from pathlib import Path

from common_library.json_serialization import json_dumps
from jinja2 import Environment, FileSystemLoader, select_autoescape

_logger = logging.getLogger(__name__)

_json_dumps_indented = partial(json_dumps, indent=2)


def create_render_environment_from_folder(top_dir: Path) -> Environment:
    assert top_dir.exists()  # nosec
    assert top_dir.is_dir()  # nosec
    env = Environment(
        loader=FileSystemLoader(top_dir),
        autoescape=select_autoescape(
            ["html", "xml"],
        ),
    )
    env.globals["dumps"] = _json_dumps_indented
    return env
