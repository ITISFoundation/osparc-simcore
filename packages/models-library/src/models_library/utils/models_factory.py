""" Collection of functions to create BaseModel subclasses

See rationale and usage of these functions in packages/models-library/tests/test_utils_models_factory.py
"""

import json
from typing import Any, Dict, Iterable, Optional, Set, Tuple, Type

from pydantic import BaseModel, create_model
from pydantic.fields import ModelField


def _collect_fields(model_cls: Type[BaseModel]) -> Dict[str, Dict[str, str]]:
    """
    Example:
        >> print(json.dumps(_collect_fields(MyModel), indent=1))

    """

    def stringify(obj):
        if callable(obj):
            return f"{getattr(obj, '__class__', None)} - {obj.__name__}"
        elif isinstance(obj, dict):
            return json.dumps(
                {f"{key}": stringify(value) for key, value in obj.items()}
            )
        elif isinstance(obj, list):
            return json.dumps([stringify(item) for item in obj])

        msg = f"{obj}"
        if "object" in msg:
            return msg.split("object")[0]
        return msg

    return {
        field.name: {
            name: stringify(getattr(field, name)) for name in ModelField.__slots__
        }
        for field in model_cls.__fields__.values()
    }


def _eval_selection(
    all_fiedls: Iterable, include: Optional[Set[str]], exclude: Optional[Set[str]]
) -> Set[str]:
    # TODO: use dict for deep include/exclude!
    # SEE
    if include is None:
        include = set(all_fiedls)
    if exclude is None:
        exclude = set()

    selection = include - exclude
    return selection


def _extract_field_definitions(
    model_cls: Type[BaseModel],
    *,
    include: Optional[Set[str]] = None,
    exclude: Optional[Set[str]] = None,
    all_optional: bool = False,
) -> Dict[str, Tuple]:
    """
    field_definitions: fields of the model
        in the format

        `<name>=(<type>, <default default>)` or `<name>=<default value>`,
         e.g.
        `foobar=(str, ...)` or `foobar=123`,

        or, for complex use-cases, in the format
        `<name>=<FieldInfo>`,
        e.g.
        `foo=Field(default_factory=datetime.utcnow, alias='bar')`

    """
    selection = _eval_selection(model_cls.__fields__.keys(), include, exclude)

    return {
        field.name: (
            # <type>
            field.type_,
            # <default value>
            field.default
            or field.default_factory
            or (None if all_optional or not field.required else ...),
        )
        for field in model_cls.__fields__.values()
        if field.name in selection
    }


# from pydantic.main import inherit_config

# def _extract_config(
#     model_cls: Type[BaseModel],
#     *,
#     include: Optional[Set[str]] = None,
#     exclude: Optional[Set[str]] = None
# ):
#     selection = _eval_selection(model_cls.__fields__.keys(), include, exclude)

#     # TODO: trim all fields based on selection!
#     namespace = {}
#     namespace["fields"] =
#     namespace["schema_extra"] =

#     return inherit_config(model_cls.__config__, model_cls.__config__, **namespace)


def copy_model(
    reference_cls: Type[BaseModel],
    *,
    name: str = None,
    include: Optional[Set[str]] = None,
    exclude: Optional[Set[str]] = None,
    as_update_model: bool = False,
    skip_validators: bool = False,
) -> Type[BaseModel]:
    """
    Creates a clone of `reference_cls` with a different name and a subset of fields


    skip_validators: when data source is already validated, there is not need to use these
    validators
    """
    name = name or f"_Base{reference_cls.__name__.upper()}"
    fields_definitions = _extract_field_definitions(
        reference_cls, exclude=exclude, include=include, all_optional=as_update_model
    )
    validators = (
        {
            f"{f}_validator": vals[0]
            for f, vals in reference_cls.__validators__.items()
            if f in fields_definitions.keys() and vals
        }
        if not skip_validators
        else None
    )

    new_model_cls = create_model(
        __model_name=name,
        __base__=BaseModel,
        __module__=reference_cls.__module__,
        __validators__=validators,
        **fields_definitions,
    )
    # new_model_cls.__doc__ = reference_cls.__doc__
    return new_model_cls
