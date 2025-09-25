from collections.abc import Callable
from typing import Any, TypeAlias

from pydantic import BaseModel, PrivateAttr, TypeAdapter

CompleteModelDict: TypeAlias = dict[str, Any]


class BaseUpdatableDisplayModel(BaseModel):
    _on_type_change_subscribers: dict[str, Callable] = PrivateAttr(default_factory=dict)
    _on_value_change_subscribers: dict[str, Callable] = PrivateAttr(
        default_factory=dict
    )

    def _get_on_change_callbacks_to_run(
        self, updates: CompleteModelDict
    ) -> list[Callable]:
        callbaks_to_run: list[Callable] = []
        for attribute, callback in self._on_value_change_subscribers.items():

            if (
                attribute in updates
                and attribute in self.__dict__
                and _are_values_different(
                    self.__dict__[attribute],
                    updates[attribute],
                    self.__class__.model_fields[attribute].annotation,
                )
            ):
                callbaks_to_run.append(callback)

        for attribute, callback in self._on_type_change_subscribers.items():
            if (
                attribute in updates
                and attribute in self.__dict__
                and _are_types_different(
                    self.__dict__[attribute],
                    updates[attribute],
                    self.__class__.model_fields[attribute].annotation,
                )
            ):
                callbaks_to_run.append(callback)

        return callbaks_to_run

    def update(self, updates: CompleteModelDict) -> None:
        """
        updates a the model properties by by reading the keys form a dcitionary
        It can also update nested models if the property is also a BaseUpdatableDisplayModel
        """

        callbacks = self._get_on_change_callbacks_to_run(updates)

        current = self.__dict__
        for key, value in updates.items():
            if key in current and current[key] != value:
                if isinstance(key, BaseUpdatableDisplayModel):
                    key.update(value)
                else:
                    setattr(self, key, value)

        for callback in callbacks:
            callback()

    def _raise_if_attribute_not_declared_in_model(self, attribute: str) -> None:
        if attribute not in self.__class__.model_fields:
            msg = f"Attribute '{attribute}' is not part of the model fields"
            raise RuntimeError(msg)

    def on_type_change(self, attribute: str, callback: Callable) -> None:
        self._raise_if_attribute_not_declared_in_model(attribute)

        self._on_type_change_subscribers[attribute] = callback

    def on_value_change(self, attribute: str, callback: Callable) -> None:
        self._raise_if_attribute_not_declared_in_model(attribute)

        self._on_value_change_subscribers[attribute] = callback


def _are_values_different(
    current_value: BaseUpdatableDisplayModel | dict,
    update_value: dict,
    annotation: type | None,
) -> bool:
    if isinstance(current_value, BaseUpdatableDisplayModel):
        return current_value != TypeAdapter(annotation).validate_python(update_value)

    return current_value != update_value


def _are_types_different(
    current_value: BaseUpdatableDisplayModel | dict,
    update_value: dict,
    annotation: type | None,
) -> bool:
    if isinstance(current_value, BaseUpdatableDisplayModel):
        return type(current_value) is not type(
            TypeAdapter(annotation).validate_python(update_value)
        )
    return type(current_value) is not type(update_value)
