from typing import Any, TypeAlias, TypeVar

from pydantic import BaseModel, Field

from .utils.string_substitution import OSPARC_IDENTIFIER_PREFIX

T = TypeVar("T")


class OsparcVariableIdentifier(BaseModel):
    # NOTE: To allow parametrized value, set the type to Union[OsparcVariableIdentifier, ...]
    osparc_variable_identifier: str = Field(
        ..., regex=rf"^\${{?{OSPARC_IDENTIFIER_PREFIX}[A-Za-z0-9_]+}}?(:-.+)?$"
    )
    replace_with: Any | None = Field(
        None, description="if not None replace the identifier with this value"
    )

    def _get_without_template_markers(self) -> str:
        # $VAR
        # ${VAR}
        # ${VAR:-}
        # ${VAR:-default}
        # ${VAR:-{}}
        if self.osparc_variable_identifier.startswith("${"):
            return self.osparc_variable_identifier.removeprefix("${").removesuffix("}")
        return self.osparc_variable_identifier.removeprefix("$")

    @property
    def osparc_variable_name(self) -> str:
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

    for attribute in pydantic_model.__dict__.values():
        if isinstance(attribute, OsparcVariableIdentifier):
            found_identifiers.append(attribute)
        elif isinstance(attribute, BaseModel):
            found_identifiers.extend(extract_identifiers(attribute))
        elif isinstance(attribute, dict):
            for value in attribute.values():
                if isinstance(value, BaseModel):
                    found_identifiers.extend(extract_identifiers(value))
        elif isinstance(attribute, list):
            for item in attribute:
                if isinstance(item, OsparcVariableIdentifier):
                    found_identifiers.append(item)
                elif isinstance(item, BaseModel):
                    found_identifiers.extend(extract_identifiers(item))

    return found_identifiers


def _resolve_in_place(pydantic_model: BaseModel) -> ResolvedIdentifiers:  # noqa: C901
    """Scans BaseModel and replaces in place  all instances of OsparcVariableIdentifier."""
    resolved_identifiers: ResolvedIdentifiers = []

    for key, attribute in dict(pydantic_model.__dict__).items():
        if isinstance(attribute, OsparcVariableIdentifier):
            if attribute.replace_with is not None:
                setattr(pydantic_model, key, attribute.replace_with)
                resolved_identifiers.append(attribute)
        elif isinstance(attribute, BaseModel):
            resolved_identifiers.extend(_resolve_in_place(attribute))
        elif isinstance(attribute, dict):
            for value in attribute.values():
                if isinstance(value, BaseModel):
                    resolved_identifiers.extend(_resolve_in_place(value))
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

    found: FoundIdentifiers = extract_identifiers(pydantic_model)

    for identifier in found:
        if identifier.osparc_variable_name in osparc_variables:
            identifier.replace_with = osparc_variables[identifier.osparc_variable_name]

    resolved: ResolvedIdentifiers = _resolve_in_place(pydantic_model)

    return found, resolved
