from copy import deepcopy
from typing import Any, TypeVar

from pydantic import BaseModel, Field

from .utils.string_substitution import OSPARC_IDENTIFIER_PREFIX

T = TypeVar("T")


class OsparcVariableIdentifier(BaseModel):
    # NOTE: To allow parametrized value, set the type to Union[OsparcVariableIdentifier, ...]
    identifier: str = Field(
        ..., regex=rf"^\${{?{OSPARC_IDENTIFIER_PREFIX}[A-Za-z0-9_]+}}?(:-.+)?$"
    )

    def _get_without_template_markers(self) -> str:
        # $VAR
        # ${VAR}
        # ${VAR:-}
        # ${VAR:-default}
        # ${VAR:-{}}
        if self.identifier.startswith("${"):
            return self.identifier.removeprefix("${").removesuffix("}")
        return self.identifier.removeprefix("$")

    @property
    def name(self) -> str:
        return self._get_without_template_markers().split(":-")[0]

    @property
    def default_value(self) -> str | None:
        parts = self._get_without_template_markers().split(":-")
        return parts[1] if len(parts) > 1 else None


class UnresolvedOsparcVariableIdentifierError(TypeError):
    def __init__(self, value: OsparcVariableIdentifier) -> None:
        super().__init__(f"Provided argument is unresolved: {value=}")


def raise_if_unresolved(var: OsparcVariableIdentifier | T) -> T:
    """Raise error or return original value

    Use like below to make linters play nice.
    ```
    def example_func(par: OsparcVariableIdentifier | int) -> None:
        _ = 12 + check_if_unresolved(par)
    ```

    Raises:
        TypeError: if the the OsparcVariableIdentifier was unresolved
    """
    if isinstance(var, OsparcVariableIdentifier):
        raise UnresolvedOsparcVariableIdentifierError(var)
    return var


def replace_osparc_variable_identifier(  # noqa: C901
    obj: T, osparc_variables: dict[str, Any]
) -> T:
    """Replaces mostly in place an instance of `OsparcVariableIdentifier` with the
    value provided inside `osparc_variables`.

    NOTE: if the provided `obj` is instance of OsparcVariableIdentifier in place
    replacement cannot be done. You need to assign it to the previous handler.

    To be safe, always use like so:
    ```
    to_replace_obj = replace_osparc_variable_identifier(to_replace_obj)

    Or like so:
    ```
    obj.to_replace_attribute =r eplace_osparc_variable_identifier(obj.to_replace_attribute)
    ```
    """

    if isinstance(obj, OsparcVariableIdentifier):
        if obj.name in osparc_variables:
            return deepcopy(osparc_variables[obj.name])
        if obj.default_value is not None:
            return deepcopy(obj.default_value)
    elif isinstance(obj, dict):
        for key, value in obj.items():
            obj[key] = replace_osparc_variable_identifier(value, osparc_variables)
    elif isinstance(obj, BaseModel):
        for key, value in obj.__dict__.items():
            obj.__dict__[key] = replace_osparc_variable_identifier(
                value, osparc_variables
            )
    if isinstance(obj, list):
        for i, item in enumerate(obj):
            obj[i] = replace_osparc_variable_identifier(item, osparc_variables)
    elif isinstance(obj, tuple):
        new_items = tuple(
            replace_osparc_variable_identifier(item, osparc_variables) for item in obj
        )
        obj = new_items
    elif isinstance(obj, set):
        new_items = {
            replace_osparc_variable_identifier(item, osparc_variables) for item in obj
        }
        obj = new_items
    return obj
