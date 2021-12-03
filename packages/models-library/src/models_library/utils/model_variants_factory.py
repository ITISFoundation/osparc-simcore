"""


The problem:


Provides a set of pydantic class models build from

"""
# SEE: https://pydantic-docs.helpmanual.io/usage/models/#dynamic-model-creation

from typing import Dict, Optional, Set, Type

from pydantic import BaseModel, Field, create_model


def extract_fields(
    reference_model: Type[BaseModel],
    *,
    include: Optional[Set[str]] = None,
    exclude: Optional[Set[str]] = None
):
    if include is None:
        include = set(reference_model.__fields__.keys())
    if exclude is None:
        exclude = set()

    selection = include - exclude

    return {
        name: (
            field.type_,
            field.default or field.default_factory or (... if field.required else None),
        )
        for name, field in reference_model.__fields__.items()
        if name in selection
    }


def create_model_for_replace_as(
    reference_model: Type[BaseModel], *, exclude: Optional[Set[str]] = None
):
    """ """
    raise NotImplementedError


def create_model_for_update_as(
    reference_model: Type[BaseModel], *, exclude: Optional[Set[str]] = None
):
    raise NotImplementedError
