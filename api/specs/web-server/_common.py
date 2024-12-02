""" Common utils for OAS script generators
"""

import inspect
import sys
from collections.abc import Callable
from pathlib import Path
from typing import (
    Annotated,
    Any,
    Generic,
    NamedTuple,
    Optional,
    TypeVar,
    Union,
    get_args,
    get_origin,
)

from common_library.json_serialization import json_dumps
from common_library.pydantic_fields_extension import get_type
from fastapi import Query
from pydantic import BaseModel, Json, create_model
from pydantic.fields import FieldInfo

CURRENT_DIR = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent


def _replace_basemodel_in_annotation(annotation, new_type):
    origin = get_origin(annotation)

    # Handle Annotated
    if origin is Annotated:
        args = get_args(annotation)
        base_type = args[0]
        metadata = args[1:]
        if isinstance(base_type, type) and issubclass(base_type, BaseModel):
            # Replace the BaseModel subclass
            base_type = new_type

        return Annotated[(base_type, *metadata)]

    # Handle Optionals, Unions, or other generic types
    if origin in (Optional, Union, list, dict, tuple):  # Extendable for other generics
        new_args = tuple(
            _replace_basemodel_in_annotation(arg, new_type)
            for arg in get_args(annotation)
        )
        return origin[new_args]

    # Replace BaseModel subclass directly
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return new_type

    # Return as-is if no changes
    return annotation


def as_query(model_class: type[BaseModel]) -> type[BaseModel]:
    fields = {}
    for field_name, field_info in model_class.model_fields.items():

        field_default = field_info.default
        assert not field_info.default_factory  # nosec
        query_kwargs = {
            "alias": field_info.alias,
            "title": field_info.title,
            "description": field_info.description,
            "metadata": field_info.metadata,
            "json_schema_extra": field_info.json_schema_extra,
        }

        annotation = _replace_basemodel_in_annotation(
            # NOTE: still missing description=query_kwargs["description"] and example=query_kwargs.get("json_schema_extra", {}).get("example_json")
            # SEE https://github.com/ITISFoundation/osparc-simcore/issues/6786
            field_info.annotation,
            new_type=Json,
        )

        if annotation != field_info.annotation:
            # Complex fields are transformed to Json
            field_default = json_dumps(field_default) if field_default else None

        fields[field_name] = (annotation, Query(default=field_default, **query_kwargs))

    new_model_name = f"{model_class.__name__}Query"
    return create_model(new_model_name, **fields)


ErrorT = TypeVar("ErrorT")


class EnvelopeE(BaseModel, Generic[ErrorT]):
    """Complementary to models_library.generics.Envelope just for the generators"""

    error: ErrorT | None = None
    data: Any | None = None


class ParamSpec(NamedTuple):
    name: str
    annotated_type: type
    field_info: FieldInfo


def assert_handler_signature_against_model(
    handler: Callable, model_cls: type[BaseModel]
):
    sig = inspect.signature(handler)

    # query, path and body parameters
    specs_params = [
        ParamSpec(param.name, param.annotation, param.default)
        for param in sig.parameters.values()
    ]

    # query and path parameters
    implemented_params = [
        ParamSpec(name, get_type(info), info)
        for name, info in model_cls.model_fields.items()
    ]

    implemented_names = {p.name for p in implemented_params}
    specified_names = {p.name for p in specs_params}

    if not implemented_names.issubset(specified_names):
        msg = f"Entrypoint {handler} does not implement OAS: {implemented_names} not in {specified_names}"
        raise AssertionError(msg)
