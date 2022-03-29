from __future__ import annotations

import collections.abc
import inspect
from inspect import Parameter, Signature
from pprint import pprint
from typing import Callable, List, NamedTuple, get_args, get_origin

from models_library.services import (
    LATEST_INTEGRATION_VERSION,
    ServiceDockerData,
    ServiceInput,
    ServiceType,
)
from pydantic import BaseModel, Field
from pydantic.tools import schema_of
from simcore_function_services.catalog import is_iterator_service
from simcore_function_services.services.iter_sensitivity import eval_sensitivity


class ServiceRecord(NamedTuple):
    meta: BaseModel  # service info + i/o
    function: Callable  # service implementation


class ServicesCatalog:
    def __init__(self, integration_version=None):
        self.services = []
        self.service_meta_model_cls = ServiceDockerData

        # catalog-wide options
        self.integration_version = integration_version or LATEST_INTEGRATION_VERSION

    def add(
        self,
        *,
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
            "integration-version": self.integration_version,
            "key": key,
            "version": version,
        }

        if inspect.iscoroutinefunction(func):
            raise NotImplementedError("Coroutines as services still not implemented")

        is_iterator = inspect.isgeneratorfunction(func)
        if is_iterator != is_iterator_service(service_key=key):
            raise ValueError(
                f"{key=} defines an iterator service but function {func.__name__} is not iterable"
            )

        #
        # inspect signature of func to retrieve inputs/output parameters
        # and annotations. This ensures consistency. Notice that parms are transmitted
        # and we need to "glue" those to the inputs/outputs
        #
        #
        signature = inspect.signature(func)
        data["inputs"] = self.validate_inputs(signature)
        data["outputs"] = self.validate_outputs(
            signature, is_iterator=inspect.isgeneratorfunction(func)
        )

        service_meta_model_cls = self.service_meta_model_cls
        self.services.append(
            ServiceRecord(meta=service_meta_model_cls(**data), function=func)
        )

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

            # FIXME: files are represented differently!

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
        # TODO: add via decorator some extra info here!
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
                        # TODO: nicer names!
                        title=f"{output_parameter}".replace("typing.", ""),
                    ),
                }
                outputs[name] = ServiceInput.parse_obj(data)
        return outputs


###-----------------------------------------------------


def test_service_catalog():
    services = ServicesCatalog()

    class Point2(BaseModel):
        x: float
        y: float

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
