import functools
import json
import logging
from pathlib import Path
from typing import Any

import notifications_library
from common_library.json_serialization import pydantic_encoder
from jinja2 import Environment, FileSystemLoader, PackageLoader, select_autoescape
from models_library.utils._original_fastapi_encoders import jsonable_encoder

_logger = logging.getLogger(__name__)


def _safe_json_dumps(obj: Any, **kwargs):
    return json.dumps(jsonable_encoder(obj), default=pydantic_encoder, **kwargs)


def create_render_environment_from_notifications_library(**kwargs) -> Environment:
    env = Environment(
        loader=PackageLoader(notifications_library.__name__, "templates"),
        autoescape=select_autoescape(["html", "xml"]),
        **kwargs
    )
    env.globals["dumps"] = functools.partial(_safe_json_dumps, indent=1)
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
    env.globals["dumps"] = functools.partial(_safe_json_dumps, indent=1)
    return env
