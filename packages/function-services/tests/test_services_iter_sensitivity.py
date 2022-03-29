from __future__ import annotations

import collections.abc
import inspect
from functools import wraps
from inspect import Parameter, Signature
from pprint import pprint
from typing import Callable, List, get_args, get_origin

from models_library.services import (
    LATEST_INTEGRATION_VERSION,
    ServiceDockerData,
    ServiceInput,
    ServiceType,
)
from pydantic import BaseModel, Field
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

    # TODO:

    def decorator(fun):
        @wraps(fun)
        def wrapper(*args, **kwargs):
            pass

        return wrapper

    return decorator


class Point2(BaseModel):
    x: float
    y: float


class ServicesCatalog:
    def __init__(self):
        self.services = {}
        self.service_meta_model_cls = ServiceDockerData

    def add(
        self,
        key,
        version,
        type,
        name=None,
        description: str = None,
        authors=None,
        contact=None,
        thumbnail=None,
        outputs=None,
    ):
        def decorator(func: Callable):
            self.add_service(key, version, func, type=type, outputs=outputs)

        return decorator

    def add_service(self, key: str, version: str, func: Callable, *, type, outputs):
        data = {
            "integration-version": LATEST_INTEGRATION_VERSION,
            "key": key,
            "version": version,
        }

        #
        # inspect signature of func to retrieve inputs/output parameters
        # and annotations.
        # This ensures consistency
        # Notice that parms are transmitted and we need to "glue"
        # those to the inputs/outputs
        #
        #
        signature = inspect.signature(func)
        inputs = self.validate_inputs(signature)
        outputs = self.validate_outputs(
            signature, is_iterator=inspect.isgeneratorfunction(func)
        )
        data.update({"inputs": inputs, "outputs": outputs})

        service_meta_model_cls = self.service_meta_model_cls
        self.services[(key, version)] = service_meta_model_cls(**data)

    def validate_inputs(self, signature: Signature):
        inputs = {}
        for parameter in signature.parameters.values():
            # should only allow keyword argument
            assert parameter.kind == parameter.KEYWORD_ONLY
            assert parameter.annotation != Parameter.empty

            # build each input
            description = getattr(
                parameter.annotation,
                "description",
                parameter.name.replace("_", " ").capitalize(),
            )

            content_schema = schema_of(
                parameter.annotation,
                title=f"{parameter.annotation}".replace("typing.", ""),
            )

            data = {
                "label": parameter.name,
                "description": description,
                "type": "ref_contentSchema",
                "contentSchema": content_schema,
            }

            if parameter.default != Parameter.empty:
                # TODO: what if partial-field defaults?
                data["defaultValue"] = parameter.default

            inputs[parameter.name] = ServiceInput.parse_obj(data)
        return inputs

    def validate_outputs(self, signature: Signature, is_iterator: bool):
        outputs = {}
        if signature.return_annotation != Signature.empty:
            origin = get_origin(signature.return_annotation)
            return_args = get_args(signature.return_annotation)

            if is_iterator:
                assert issubclass(origin, collections.abc.Iterable)

            if issubclass(origin, collections.abc.Iterable):
                origin = get_origin(return_args[0])
                return_args = get_args(return_args[0])

            if not issubclass(origin, tuple):
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
        return outputs


services = ServicesCatalog()


@services.add(key="foo", version="1.2.3", type=ServiceType.BACKEND)
def my_function_service(
    x1: int,
    x2: float,
    x3: str,
    x4: List[float] = Field(..., x_unit="mm"),
    x5: Point2 = ...,
) -> Point2:
    # check function that ensures dask can transmit this function |<<<<----
    pass


###-----------------------------------------------------


def test_it():
    # get signature
    signature: Signature = inspect.signature(eval_sensitivity)

    assert not inspect.iscoroutinefunction(eval_sensitivity)
    #  TODO: check against meta??
    assert inspect.isgeneratorfunction(eval_sensitivity)

    is_iterator = inspect.isgeneratorfunction(eval_sensitivity)

    inputs = {}

    for parameter in signature.parameters.values():
        # should only allow keyword argument
        assert parameter.kind == parameter.KEYWORD_ONLY
        assert parameter.annotation != Parameter.empty

        # build each input
        description = getattr(
            parameter.annotation,
            "description",
            parameter.name.replace("_", " ").capitalize(),
        )

        content_schema = schema_of(
            parameter.annotation, title=f"{parameter.annotation}".replace("typing.", "")
        )

        data = {
            "label": parameter.name,
            "description": description,
            "type": "ref_contentSchema",
            "contentSchema": content_schema,
        }

        if parameter.default != Parameter.empty:
            # TODO: what if partial-field defaults?
            data["defaultValue"] = parameter.default

        inputs[parameter.name] = ServiceInput.parse_obj(data)

    outputs = {}
    if signature.return_annotation != Signature.empty:
        origin = get_origin(signature.return_annotation)
        return_args = get_args(signature.return_annotation)

        if is_iterator:
            assert issubclass(origin, collections.abc.Iterable)

        if issubclass(origin, collections.abc.Iterable):
            origin = get_origin(return_args[0])
            return_args = get_args(return_args[0])

        if not issubclass(origin, tuple):
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

    pprint({"inputs": inputs, "outputs": outputs})
    print("-" * 100)
