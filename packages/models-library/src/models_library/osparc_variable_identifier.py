from copy import deepcopy
from typing import Any, TypeAlias, TypeVar

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


FoundIdentifiers: TypeAlias = list[OsparcVariableIdentifier]
ResolvedIdentifiers: TypeAlias = list[OsparcVariableIdentifier]


def extract_identifiers(pydantic_model: BaseModel) -> FoundIdentifiers:  # noqa: C901
    """Scans BaseModel and all it's attributes where and returns
    all found OsparcVariableIdentifier.
    """
    found_identifiers: FoundIdentifiers = []

    for key, attribute in pydantic_model.__dict__.items():
        if isinstance(attribute, OsparcVariableIdentifier):
            found_identifiers.append(attribute)
        elif isinstance(attribute, BaseModel):
            found_identifiers.extend(extract_identifiers(attribute))
        elif isinstance(attribute, dict):
            for value in attribute.values():
                if isinstance(value, OsparcVariableIdentifier):
                    found_identifiers.append(value)
                elif isinstance(value, BaseModel):
                    found_identifiers.extend(extract_identifiers(value))
        elif isinstance(attribute, list):
            for item in attribute:
                if isinstance(item, OsparcVariableIdentifier):
                    found_identifiers.append(item)
                elif isinstance(item, BaseModel):
                    found_identifiers.extend(extract_identifiers(item))

    return found_identifiers


def _resolve_in_place(an_object: object) -> ResolvedIdentifiers:  # noqa: C901
    """Scans BaseModel and replaces in place  all instances of OsparcVariableIdentifier."""
    resolved_identifiers: ResolvedIdentifiers = []

    # write replace in BaseModel
    # write replace in list
    # write replace in dict

    soruce_object_dict = (
        an_object if isinstance(an_object, dict) else an_object.__dict__
    )

    for key, attribute in soruce_object_dict.items():
        if isinstance(attribute, OsparcVariableIdentifier):
            if attribute.replace_with is not None:
                setattr(soruce_object_dict, key, attribute.replace_with)
                resolved_identifiers.append(attribute)
        elif isinstance(attribute, BaseModel):
            resolved_identifiers.extend(_resolve_in_place(attribute))
        elif isinstance(attribute, dict):
            resolved_identifiers.extend(_resolve_in_place(attribute))
            # for dict_key in list(attribute.keys()):
            #     value = attribute[dict_key]
            #     if isinstance(value, OsparcVariableIdentifier):
            #         if value.replace_with is not None:
            #             resolved_identifiers.append(value)
            #             attribute[dict_key] = value.replace_with
            #     elif isinstance(value, BaseModel):
            #         resolved_identifiers.extend(_resolve_in_place(value))
        elif isinstance(attribute, list):
            for k in range(len(attribute)):
                if isinstance(attribute[k], OsparcVariableIdentifier):
                    if attribute[k].replace_with is not None:
                        resolved_identifiers.append(attribute[k])
                        attribute[k] = attribute[k].replace_with
                elif isinstance(attribute[k], BaseModel):
                    resolved_identifiers.extend(_resolve_in_place(attribute[k]))

    return resolved_identifiers


def resolve_osparc_variable_identifiers(
    pydantic_model: BaseModel, osparc_variables: dict[str, Any]
) -> tuple[FoundIdentifiers, ResolvedIdentifiers]:
    """Replaces inside the model the instances of `OsparcVariableIdentifier`
    with the values provided inside `osparc_variables`.

    Arguments:
        pydantic_model -- model on which replacement will be applied
        osparc_variables -- osparc variable names names and their values

    Returns:
        a tuple containing the found identifiers and the ones which were replaced
    """

    if isinstance(pydantic_model, OsparcVariableIdentifier):
        msg = f"Cannot replace variables if root element is {OsparcVariableIdentifier}"
        raise TypeError(msg)

    found: FoundIdentifiers = extract_identifiers(pydantic_model)

    for identifier in found:
        if identifier.name in osparc_variables:
            identifier.replace_with = osparc_variables[identifier.name]

    resolved: ResolvedIdentifiers = _resolve_in_place(pydantic_model)

    return found, resolved


def replace_osparc_variable_identifier(  # noqa: C901
    obj: T, osparc_variables: dict[str, Any]
) -> T:
    if isinstance(obj, OsparcVariableIdentifier):
        if obj.name in osparc_variables:
            return deepcopy(osparc_variables[obj.name])
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
