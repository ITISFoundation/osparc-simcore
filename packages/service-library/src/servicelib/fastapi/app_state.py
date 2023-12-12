import logging

from fastapi import FastAPI

_logger = logging.getLogger(__name__)


class SingletonInAppStateMixin:
    """
    Mixin to get, set and delete an instance of 'self' from/to app.state
    """

    app_state_name: str  # Name used in app.state.$(app_state_name)
    frozen: bool = True  # Will raise if set multiple times

    @classmethod
    def get_from_app_state(cls, app: FastAPI):
        return getattr(app.state, cls.app_state_name)

    def set_to_app_state(self, app: FastAPI):
        if (exists := getattr(app.state, self.app_state_name, None)) and self.frozen:
            msg = f"An instance of {type(self)} already in app.state.{self.app_state_name}={exists}"
            raise ValueError(msg)

        setattr(app.state, self.app_state_name, self)
        return self.get_from_app_state(app)

    @classmethod
    def pop_from_app_state(cls, app: FastAPI):
        """
        Raises:
            AttributeError: if instance is not in app.state
        """
        old = getattr(app.state, cls.app_state_name)
        delattr(app.state, cls.app_state_name)
        return old
