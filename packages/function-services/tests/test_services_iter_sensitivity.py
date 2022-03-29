from __future__ import annotations

import inspect
import json
from functools import wraps
from inspect import Parameter, Signature
from typing import Iterable, Iterator, List, Tuple, get_args, get_origin

from models_library.services import (
    LATEST_INTEGRATION_VERSION,
    ServiceInput,
    ServiceType,
)
from pydantic import BaseModel
from pydantic.tools import schema_of
from simcore_function_services.services.iter_sensitivity import eval_sensitivity


def service(
    key,
    version,
    type,
    name=None,
    description=None,
    authors=None,
    contact=None,
    thumbnail=None,
):
    # meta info passed via the decorator
    info = {
        "integration-version": LATEST_INTEGRATION_VERSION,
        "key": key,
        "version": version,
    }

    # TODO:

    def decorator(fun):
        # TODO: extract inputs from signature
        # TODO: extract outputs from signature

        @wraps(fun)
        def wrapper(*args, **kwargs):
            pass

        return wrapper

    return decorator


class Point2(BaseModel):
    x: float
    y: float


@service(key="foo", version="1.2.3", type=ServiceType.BACKEND)
def my_function_service(
    x1: int, x2: float, x3: str, x4: List[float], x5: Point2
) -> Point2:
    # check function that ensures dask can transmit this function |<<<<----
    pass


def test_it():
    # get signature
    signature: Signature = inspect.signature(eval_sensitivity)

    inputs = {}

    for parameter in signature.parameters.values():
        # should only allow keyword argument
        assert parameter.kind == parameter.KEYWORD_ONLY
        assert parameter.annotation != Parameter.empty

        # build each input
        data = {
            "label": parameter.name,
            "description": getattr(
                parameter.annotation, "description", parameter.name
            ).capitalize(),
            "type": "ref_contentSchema",
            "contentSchema": schema_of(
                parameter.annotation,
                title=f"{parameter.annotation}".replace("typing.", ""),
            ),
        }

        if parameter.default != Parameter.empty:
            data["defaultValue"] = parameter.default

        inputs[parameter.name] = ServiceInput.parse_obj(data)

    outputs = {}
    if signature.return_annotation != Signature.empty:
        origin = get_origin(signature.return_annotation)
        return_args = get_args(signature.return_annotation)

        if origin in (Iterable, Iterator):
            # this is an iterator
            origin = get_origin(return_args)

        if origin != Tuple:
            return_args = signature.return_annotation

        for index, output_parameter in enumerate(return_args, start=1):
            name = f"out_{index}"
            data = {
                "label": name,
                "description": "",
                "type": "ref_contentSchema",
                "contentSchema": schema_of(
                    output_parameter,
                    title=f"{output_parameter}".replace("typing.", ""),
                ),
            }
            outputs[name] = ServiceInput.parse_obj(data)

    print(json.dumps({"inputs": inputs, "outputs": outputs}), indent=1)
    print("-" * 100)
