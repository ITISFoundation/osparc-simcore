# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
import pytest
from pydantic import BaseModel
from faker import Faker

from models_library.projects import Project, Position

fake = Faker()


import pydantic

from typing import Dict, Any, Type
from pydantic import BaseModel


class Person(BaseModel):
    name: str
    age: int

    class Config:
        @staticmethod
        def schema_extra(schema: Dict[str, Any], model: Type['Person']) -> None:
            for prop in schema.get('properties', {}).values():
                prop.pop('title', None)


def create_fake():

    model_cls = Position
    for name, field in model_cls.__fields__:

        if field.is_complex():
            # iterate

            if field.required:
                # if fake function in place
                if hasattr(model_cls, "fake"):
                    value = model_cls.fake()

        else:

            if field.required:
                # if fake function in place

                if hasattr(model_cls, "fake"):
                    value = model_cls.fake()

                value = field.get_default()

                value = field.field_info.extra.get("example")

                # build a fake based in type and all constraints
                #

                #
                # field.field_info.type_
                #
                """
                    :param default: since this is replacing the field’s default, its first argument is used to set the default, use ellipsis (``...``) to indicate the field is required
                    :param default_factory: callable that will be called when a default value is needed for this field If both `default` and `default_factory` are set, an error is raised.
                    :param alias: the public name of the field
                    :param title: can be any string, used in the schema
                    :param description: can be any string, used in the schema
                    :param const: this field is required and *must* take it's default value
                    :param gt: only applies to numbers, requires the field to be "greater than". The schema will have an ``exclusiveMinimum`` validation keyword
                    :param ge: only applies to numbers, requires the field to be "greater than or equal to". The schema will have a ``minimum`` validation keyword
                    :param lt: only applies to numbers, requires the field to be "less than". The schema will have an ``exclusiveMaximum`` validation keyword
                    :param le: only applies to numbers, requires the field to be "less than or equal to". The schema will have a ``maximum`` validation keyword
                    :param multiple_of: only applies to numbers, requires the field to be "a multiple of". The schema will have a ``multipleOf`` validation keyword
                    :param min_length: only applies to strings, requires the field to have a minimum length. The schema will have a ``maximum`` validation keyword
                    :param max_length: only applies to strings, requires the field to have a maximum length. The schema will have a ``maxLength`` validation keyword
                    :param regex: only applies to strings, requires the field match agains a regular expression pattern string. The schema will have a ``pattern`` validation keyword
                    :param **extra: any additional keyword arguments will be added as is to the schema
                """

    # for field in model.__fie
    # navigate fields
    # if example cls.Config.schema_extra.get("example")
    # type
    # default or some value in fake
