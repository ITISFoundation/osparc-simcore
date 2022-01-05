""" Collection of functions to create BaseModel subclasses


Maintaining large models representing resource can be challenging, specially when every interface needs a slightly
different variation of the original domain model. For instance, assume we want to implement an API with CRUD routes on a resource R.
This needs similar models for the request bodies and response payloads to represent R. A careful analysis reveals that
these models are all basically variants that include/exclude fields and/or changes constraints on them (e.g. read-only,
nullable, optional/required, etc).

This is typically achived by splitting common fields into smaller models and using inheritance to compose them back and/or override
constraints. Nonetheless, this approach can be very tedious to maintain: it is very verbose and difficult to see the final model
layout. In addition, new variants that exclude fields will force to redesign how all models were split in the first place.

In order to overcome these contraints, this model presents here a functional approach base on a model's factory that can "copy"
necessary parts from a base model and create a new model class of out of it.

The design should remain as close to pydantic's jargon/naming as possible to reduce maintenance costs
since we are aware that future releases of pydantic will address part of the features we implement here (e.g. exclude fields)

Usage of these tools are demonstrated in packages/models-library/tests/test_utils_models_factory.py
"""

import json
from typing import Dict, Iterable, Optional, Set, Tuple, Type

from pydantic import BaseModel, create_model
from pydantic.fields import ModelField


def _collect_fields_attrs(model_cls: Type[BaseModel]) -> Dict[str, Dict[str, str]]:
    """
    Example:
        >> print(json.dumps(_collect_fields(MyModel), indent=1))

    """

    def _stringify(obj):
        if callable(obj):
            return f"{getattr(obj, '__class__', None)} - {obj.__name__}"
        if isinstance(obj, dict):
            return json.dumps(
                {f"{key}": _stringify(value) for key, value in obj.items()}
            )
        if isinstance(obj, list):
            return json.dumps([_stringify(item) for item in obj])

        msg = f"{obj}"
        if "object" in msg:
            return msg.split("object")[0]
        return msg

    return {
        field.name: {
            attr_name: _stringify(getattr(field, attr_name))
            for attr_name in ModelField.__slots__
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
