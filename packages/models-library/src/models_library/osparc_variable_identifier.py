import os
from copy import deepcopy
from typing import Annotated, Any, Final, TypeVar

from common_library.errors_classes import OsparcErrorMixin
from models_library.basic_types import ConstrainedStr
from pydantic import BaseModel, Discriminator, PositiveInt, Tag

from .utils.string_substitution import OSPARC_IDENTIFIER_PREFIX
from .utils.types import get_types_from_annotated_union

T = TypeVar("T")


class _BaseOsparcVariableIdentifier(ConstrainedStr):
    # NOTE: To allow parametrized value, set the type to Union[OsparcVariableIdentifier, ...]
    # NOTE: When dealing with str types, to avoid unexpected behavior, the following
    # order is suggested `OsparcVariableIdentifier | str`

    def _get_without_template_markers(self) -> str:
        # $VAR
        # ${VAR}
        # ${VAR:-}
        # ${VAR:-default}
        # ${VAR:-{}}
        return (
            self.removeprefix("$$")
            .removeprefix("$")
            .removeprefix("{")
            .removesuffix("}")
        )

    @property
    def name(self) -> str:
        return self._get_without_template_markers().split(":-")[0]

    @property
    def default_value(self) -> str | None:
        parts = self._get_without_template_markers().split(":-")
        return parts[1] if len(parts) > 1 else None

    @staticmethod
    def get_pattern(max_dollars: PositiveInt) -> str:
        # NOTE: in below regex `{`` and `}` are respectively escaped with `{{` and `}}`
        return rf"^\${{1,{max_dollars}}}(?:\{{)?{OSPARC_IDENTIFIER_PREFIX}[A-Za-z0-9_]+(?:\}})?(:-.+)?$"


class PlatformOsparcVariableIdentifier(_BaseOsparcVariableIdentifier):
    pattern = _BaseOsparcVariableIdentifier.get_pattern(max_dollars=2)


class OoilOsparcVariableIdentifier(_BaseOsparcVariableIdentifier):
    pattern = _BaseOsparcVariableIdentifier.get_pattern(max_dollars=4)


_PLATFORM: Final[str] = "platform"
_OOIL_VERSION: Final[str] = "ooil-version"


def _get_discriminator_value(v: Any) -> str:
    _ = v
    if os.environ.get("ENABLE_OOIL_OSPARC_VARIABLE_IDENTIFIER", None):
        return _OOIL_VERSION

    return _PLATFORM


OsparcVariableIdentifier = Annotated[
    (
        Annotated[PlatformOsparcVariableIdentifier, Tag(_PLATFORM)]
        | Annotated[OoilOsparcVariableIdentifier, Tag(_OOIL_VERSION)]
    ),
    Discriminator(_get_discriminator_value),
]


class UnresolvedOsparcVariableIdentifierError(OsparcErrorMixin, TypeError):
    msg_template = "Provided argument is unresolved: value={value}"


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
    if isinstance(var, get_types_from_annotated_union(OsparcVariableIdentifier)):
        raise UnresolvedOsparcVariableIdentifierError(value=var)
    return var  # type: ignore[return-value]


def replace_osparc_variable_identifier(  # noqa: C901
    obj: T, osparc_variables: dict[str, Any]
) -> T:
    """Replaces mostly in place an instance of `OsparcVariableIdentifier` with the
    value provided inside `osparc_variables`.

    NOTE: when using make sure that `obj` is of type `BaseModel` or
    `OsparcVariableIdentifier` otherwise it will nto work as intended.

    NOTE: if the provided `obj` is instance of OsparcVariableIdentifier in place
    replacement cannot be done. You need to assign it to the previous handler.

    To be safe, always use like so:
    ```
    to_replace_obj = replace_osparc_variable_identifier(to_replace_obj)

    Or like so:
    ```
    obj.to_replace_attribute = replace_osparc_variable_identifier(obj.to_replace_attribute)
    ```
    """

    if isinstance(obj, get_types_from_annotated_union(OsparcVariableIdentifier)):
        if obj.name in osparc_variables:  # type: ignore[attr-defined]
            return deepcopy(osparc_variables[obj.name])  # type: ignore[no-any-return,attr-defined]
        if obj.default_value is not None:  # type: ignore[attr-defined]
            return deepcopy(obj.default_value)  # type: ignore[no-any-return,attr-defined]
    elif isinstance(obj, dict):
        for key, value in obj.items():
            obj[key] = replace_osparc_variable_identifier(value, osparc_variables)
    elif isinstance(obj, BaseModel):
        for key, value in obj.__dict__.items():
            obj.__dict__[key] = replace_osparc_variable_identifier(
                value, osparc_variables
            )
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            obj[i] = replace_osparc_variable_identifier(item, osparc_variables)
    elif isinstance(obj, tuple):
        new_tuple = tuple(
            replace_osparc_variable_identifier(item, osparc_variables) for item in obj
        )
        obj = new_tuple  # type: ignore
    elif isinstance(obj, set):
        new_set = {
            replace_osparc_variable_identifier(item, osparc_variables) for item in obj
        }
        obj = new_set  # type: ignore
    return obj


def raise_if_unresolved_osparc_variable_identifier_found(obj: Any) -> None:
    """
    NOTE: when using make sure that `obj` is of type `BaseModel` or
    `OsparcVariableIdentifier` otherwise it will nto work as intended.

    Raises:
        UnresolvedOsparcVariableIdentifierError: if not all instances of
        `OsparcVariableIdentifier` were replaced
    """
    if isinstance(obj, get_types_from_annotated_union(OsparcVariableIdentifier)):
        raise_if_unresolved(obj)
    elif isinstance(obj, dict):
        for key, value in obj.items():
            raise_if_unresolved_osparc_variable_identifier_found(key)
            raise_if_unresolved_osparc_variable_identifier_found(value)
    elif isinstance(obj, BaseModel):
        for value in obj.__dict__.values():
            raise_if_unresolved_osparc_variable_identifier_found(value)
    elif isinstance(obj, list | tuple | set):
        for item in obj:
            raise_if_unresolved_osparc_variable_identifier_found(item)
