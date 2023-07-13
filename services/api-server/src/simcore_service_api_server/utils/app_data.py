"""
    AppData refers to instances of dataclasses stored in the FastApi application
"""
from fastapi import FastAPI


class AppDataMixin:
    """
    appdata is a unique entry of app's state

    This mixin adds a mechanism to reliably create, get and delete instances
    of the derived class
    """

    state_attr_name: str | None = None

    @classmethod
    def create_once(cls, app: FastAPI, **data):
        """Creates a single instance in app context"""

        obj = cls.get_instance(app)
        if obj is None:
            assert issubclass(cls, AppDataMixin)  # nosec
            cls.state_attr_name = f"unique_{cls.__name__.lower()}"

            # creates dataclass instance
            obj = cls(**data)

            # injects in app.state
            setattr(app.state, cls.state_attr_name, obj)

        return obj

    @classmethod
    def get_instance(cls, app: FastAPI):
        """Gets single instance in app if any, otherwise returns None"""
        assert issubclass(cls, AppDataMixin)  # nosec

        if cls.state_attr_name is None:
            return None
        assert isinstance(cls.state_attr_name, str)  # nosec

        return getattr(app.state, cls.state_attr_name, None)

    @classmethod
    def pop_instance(cls, app: FastAPI):
        assert issubclass(cls, AppDataMixin)  # nosec

        obj = cls.get_instance(app)
        if obj and cls.state_attr_name:
            delattr(app.state, cls.state_attr_name)
        return obj
