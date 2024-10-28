from typing import Any, NamedTuple, TypeAlias, cast

from common_library.errors_classes import OsparcErrorMixin
from common_library.json_serialization import json_dumps, json_loads
from pydantic import StrictBool, StrictFloat, StrictInt

from .string_substitution import (
    SubstitutionsDict,
    TextTemplate,
    substitute_all_legacy_identifiers,
)

# This constraint on substitution values is to avoid
# deserialization issues on the TextTemplate substitution!
SubstitutionValue: TypeAlias = StrictBool | StrictInt | StrictFloat | str


class IdentifierSubstitutionError(OsparcErrorMixin, KeyError):
    msg_template: str = (
        "Was not able to substitute identifier "
        "'{name}'. It was not found in: {substitutions}"
    )


class _EnvVarData(NamedTuple):
    substitution_identifier: str
    identifier_name: str
    default_value: Any | None


class SpecsSubstitutionsResolver:
    """
    Resolve specs dict by substituting identifiers

    'specs' is defined here as dict[str, Any]. E.g. a docker-compose.yml loaded as a dict are 'specs'.

    """

    def __init__(self, specs: dict[str, Any], *, upgrade: bool):
        self._template = self._create_text_template(specs, upgrade=upgrade)
        self._substitutions: SubstitutionsDict = SubstitutionsDict()

    @classmethod
    def _create_text_template(
        cls, specs: dict[str, Any], *, upgrade: bool
    ) -> TextTemplate:
        # convert to yaml (less symbols as in json)
        service_spec_str: str = json_dumps(specs)

        if upgrade:  # legacy
            service_spec_str = substitute_all_legacy_identifiers(service_spec_str)

        # template
        template = TextTemplate(service_spec_str)
        assert template.is_valid()  # nosec

        return template

    def get_identifiers(self) -> list[str]:
        """lists identifiers in specs in order of apperance. Can have repetitions"""
        output: list[str] = self._template.get_identifiers()
        return output

    def get_replaced(self) -> set[str]:
        return self._substitutions.used

    @property
    def substitutions(self):
        return self._substitutions

    def set_substitutions(
        self, mappings: dict[str, SubstitutionValue]
    ) -> SubstitutionsDict:
        """
        NOTE: ONLY targets identifiers declared in the specs
        NOTE:`${identifier:-a_default_value}` will replace the identifier with `a_default_value`
        if not provided
        """

        required_identifiers = self.get_identifiers()

        required_identifiers_with_defaults: list[_EnvVarData] = []
        for identifier in required_identifiers:
            parts = identifier.split(":-", maxsplit=1)
            required_identifiers_with_defaults.append(
                _EnvVarData(
                    substitution_identifier=identifier,
                    identifier_name=parts[0],
                    default_value=(
                        parts[1] if len(parts) == 2 else None  # noqa: PLR2004
                    ),
                )
            )

        resolved_identifiers: dict[str, str] = {}
        for env_var_data in required_identifiers_with_defaults:
            if env_var_data.identifier_name in mappings:
                resolved_identifiers[env_var_data.substitution_identifier] = cast(
                    str, mappings[env_var_data.identifier_name]
                )
            # NOTE: default is used only if not found in the provided substitutions
            elif env_var_data.default_value is not None:
                resolved_identifiers[
                    env_var_data.substitution_identifier
                ] = env_var_data.default_value

        # picks only needed for substitution
        self._substitutions = SubstitutionsDict(resolved_identifiers)
        return self._substitutions

    def run(self, *, safe: bool = True) -> dict[str, Any]:
        """
        Keyword Arguments:
            safe -- if False will raise an error if not all identifiers
                are substituted (default: {True})

        Raises:
            IdentifierSubstitutionError: when identifier is not found and safe is False
        """
        try:
            new_specs_txt: str = (
                self._template.safe_substitute(self._substitutions)
                if safe
                else self._template.substitute(self._substitutions)
            )
            new_specs = json_loads(new_specs_txt)
            assert isinstance(new_specs, dict)  # nosec
            return new_specs
        except KeyError as e:
            raise IdentifierSubstitutionError(
                name=e.args[0], substitutions=self._substitutions
            ) from e
