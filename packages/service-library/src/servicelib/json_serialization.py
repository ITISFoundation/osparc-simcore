import json
from typing import Any

from models_library.utils.fastapi_encoders import jsonable_encoder
from pydantic.json import pydantic_encoder


def json_dumps(obj: Any, **kwargs):
    """json.dumps with rich encoder.
    A big applause for pydantic authors here!!!
    """
    return json.dumps(obj, default=pydantic_encoder, **kwargs)


def safe_json_dumps(obj: Any, **kwargs):
    return json_dumps(jsonable_encoder(obj), **kwargs)
