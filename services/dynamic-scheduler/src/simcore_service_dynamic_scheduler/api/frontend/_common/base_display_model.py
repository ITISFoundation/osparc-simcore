from functools import cached_property
from typing import Any, TypeAlias

from pydantic import BaseModel, TypeAdapter

CompleteModelDict: TypeAlias = dict[str, Any]


class BaseUpdatableDisplayModel(BaseModel):

    @cached_property
    def rerender_on_value_change(self) -> set[str]:
        """
        redefine in subclasses to return a set of `attribute` names that
        cause a rerender when their `values` change
        """
        return set()

    @cached_property
    def rerender_on_type_change(self) -> set[str]:
        """
        redefine in subclasses to return a set of `attribute` names that
        cause a rerender when their `types` change
        """
        return set()

    def requires_rerender(self, updates: CompleteModelDict) -> bool:
        """True when any changes occur to any of the:
        - `values` of the attribute names declared by `get_rerender_on_value_change`
        - `types` of of the attribute names declared by `get_rerender_on_type_change`
        """
        requires_rerender: bool = False

        for key in self.rerender_on_value_change:
            if (
                key in updates
                and key in self.__dict__
                and _are_values_different(
                    self.__dict__[key],
                    updates[key],
                    self.__class__.model_fields[key].annotation,
                )
            ):
                requires_rerender = True
                break

        for key in self.rerender_on_type_change:
            if (
                key in updates
                and key in self.__dict__
                and _are_types_different(
                    self.__dict__[key],
                    updates[key],
                    self.__class__.model_fields[key].annotation,
                )
            ):
                requires_rerender = True
                break

        return requires_rerender

    def update(self, updates: CompleteModelDict) -> None:
        """
        updates a the model properties by by reading the keys form a dcitionary
        It can also update nested models if the property is also a BaseUpdatableDisplayModel
        """
        current = self.__dict__
        for key, value in updates.items():
            if key in current and current[key] != value:
                if isinstance(key, BaseUpdatableDisplayModel):
                    key.update(value)
                else:
                    setattr(self, key, value)


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


def _are_values_different(
    current_value: BaseUpdatableDisplayModel | dict,
    update_value: dict,
    annotation: type | None,
) -> bool:
    if isinstance(current_value, BaseUpdatableDisplayModel):
        return current_value != TypeAdapter(annotation).validate_python(update_value)

    return current_value != update_value
