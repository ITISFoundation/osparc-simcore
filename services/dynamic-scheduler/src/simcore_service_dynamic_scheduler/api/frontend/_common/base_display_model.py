from collections.abc import Callable
from typing import Any, Self, TypeAlias

from pydantic import BaseModel, NonNegativeInt, PrivateAttr

CompleteModelDict: TypeAlias = dict[str, Any]


class BaseUpdatableDisplayModel(BaseModel):
    _on_type_change_subscribers: dict[str, Callable] = PrivateAttr(default_factory=dict)
    _on_value_change_subscribers: dict[str, Callable] = PrivateAttr(
        default_factory=dict
    )

    def _get_on_change_callbacks_to_run(self, update_obj: Self) -> list[Callable]:
        callbaks_to_run: list[Callable] = []

        for attribute_name, callback in self._on_value_change_subscribers.items():
            if getattr(self, attribute_name) != getattr(update_obj, attribute_name):
                callbaks_to_run.append(callback)

        for attribute_name, callback in self._on_type_change_subscribers.items():
            if type(getattr(self, attribute_name)) is not type(
                getattr(update_obj, attribute_name)
            ):
                callbaks_to_run.append(callback)

        return callbaks_to_run

    def update(self, update_obj: Self) -> NonNegativeInt:
        """
        updates the model with the values from update_obj
        returns the number of callbacks that were run
        """
        callbacks_to_run = self._get_on_change_callbacks_to_run(update_obj)

        for attribute_name, update_value in update_obj.__dict__.items():
            current_value = getattr(self, attribute_name)
            if current_value != update_value:
                if isinstance(update_value, BaseUpdatableDisplayModel):
                    if type(current_value) is type(update_value):
                        # when the same type update the existing object
                        current_value.update(update_value)
                    else:
                        setattr(self, attribute_name, update_value)

                setattr(self, attribute_name, update_value)

        for callback in callbacks_to_run:
            callback()

        return len(callbacks_to_run)

    def _raise_if_attribute_not_declared_in_model(self, attribute: str) -> None:
        if attribute not in self.__class__.model_fields:
            msg = f"Attribute '{attribute}' is not part of the model fields"
            raise ValueError(msg)

    def on_type_change(self, attribute: str, callback: Callable) -> None:
        """subscribe callback to an attribute TYPE change"""
        self._raise_if_attribute_not_declared_in_model(attribute)

        self._on_type_change_subscribers[attribute] = callback

    def on_value_change(self, attribute: str, callback: Callable) -> None:
        """subscribe callback to an attribute VALUE change"""
        self._raise_if_attribute_not_declared_in_model(attribute)

        self._on_value_change_subscribers[attribute] = callback
