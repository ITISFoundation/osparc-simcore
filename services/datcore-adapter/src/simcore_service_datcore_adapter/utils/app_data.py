"""
    AppData refers to instances of dataclasses stored in the FastApi application
"""
from dataclasses import dataclass
from typing import ClassVar

from fastapi import FastAPI


@dataclass
class AppDataMixin:
    """
    appdata preserves a single instance of the data within an app context

    This mixin adds a mechanism to reliably create, get and delete instances
    of the derived class
    """

    state_attr_name: ClassVar[str]

    @classmethod
    def create_once(cls, app: FastAPI, **data):
        """Creates a single instance in app"""

        obj = cls.get_instance(app)
        if not obj:
            assert issubclass(cls, AppDataMixin), "AppDataMixin must be inherited!"
            cls.state_attr_name = f"unique_{cls.__name__.lower()}"

            # creates dataclass instance
            obj = cls(**data)

            # injects in app.state
            setattr(app.state, cls.state_attr_name, obj)

        return obj

    @classmethod
    def get_instance(cls, app: FastAPI):
        """Gets single instance in app if any, otherwise returns None"""
        assert issubclass(cls, AppDataMixin), "AppDataMixin must be inherited!"

        try:
            obj = getattr(app.state, cls.state_attr_name)
        except AttributeError:
            # not in app.state or state_attr_name undefined
            return None
        return obj

    @classmethod
    def pop_instance(cls, app: FastAPI):
        assert issubclass(cls, AppDataMixin), "AppDataMixin must be inherited!"

        obj = cls.get_instance(app)
        if obj:
            delattr(app.state, cls.state_attr_name)
        return obj
