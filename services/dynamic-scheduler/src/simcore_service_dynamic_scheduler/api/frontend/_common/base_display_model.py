from collections.abc import Callable
from typing import Annotated, Any, Self, TypeAlias

from pydantic import BaseModel, NonNegativeInt, PrivateAttr

CompleteModelDict: TypeAlias = dict[str, Any]


class BaseUpdatableDisplayModel(BaseModel):
    _on_type_change_subscribers: Annotated[
        dict[str, Callable], PrivateAttr(default_factory=dict)
    ]
    _on_value_change_subscribers: Annotated[
        dict[str, Callable], PrivateAttr(default_factory=dict)
    ]
    _on_remove_from_ui_callback: Annotated[Callable | None, PrivateAttr(default=None)]

    def _get_on_change_callbacks_to_run(self, update_obj: Self) -> list[Callable]:
        callbacks_to_run: list[Callable] = []

        for attribute_name, callback in self._on_value_change_subscribers.items():
            if getattr(self, attribute_name) != getattr(update_obj, attribute_name):
                callbacks_to_run.append(callback)

        for attribute_name, callback in self._on_type_change_subscribers.items():
            if type(getattr(self, attribute_name)) is not type(
                getattr(update_obj, attribute_name)
            ):
                callbacks_to_run.append(callback)

        return callbacks_to_run

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
                        current_value.update(update_value)
                    else:
                        setattr(self, attribute_name, update_value)
                else:
                    setattr(self, attribute_name, update_value)

        for callback in callbacks_to_run:
            callback()

        return len(callbacks_to_run)

    def remove_from_ui(self) -> None:
        """the UI will remove the component associated with this model"""
        if self._on_remove_from_ui_callback:
            self._on_remove_from_ui_callback()

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

    def on_remove_from_ui(self, callback: Callable) -> None:
        """
        invokes callback when object is no longer required,
        allows the UI to have a clear hook to remove the component
        """
        self._on_remove_from_ui_callback = callback
