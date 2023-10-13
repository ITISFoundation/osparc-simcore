import json
from typing import Any, TypeAlias, cast

from pydantic import StrictBool, StrictFloat, StrictInt
from pydantic.errors import PydanticErrorMixin

from .string_substitution import (
    SubstitutionsDict,
    TextTemplate,
    substitute_all_legacy_identifiers,
)

# This constraint on substitution values is to avoid
# deserialization issues on the TextTemplate substitution!
SubstitutionValue: TypeAlias = StrictBool | StrictInt | StrictFloat | str


def _json_dumps(data: dict[str, Any]) -> str:
    return json.dumps(data)


def _json_loads(str_data: str) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(str_data))


class IdentifierSubstitutionError(PydanticErrorMixin, KeyError):
    msg_template: str = (
        "Was not able to substitute identifier "
        "'{name}'. It was not found in: {substitutions}"
    )


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
        service_spec_str: str = _json_dumps(specs)

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

        required_identifiers_with_defaults: dict[str, str | None] = {}
        for identifier in required_identifiers:
            parts = identifier.split(":-")
            required_identifiers_with_defaults[identifier] = (
                parts[1] if ":-" in identifier else None
            )

        resolved_identifiers: dict[str, str] = {}
        for identifier, default_value in required_identifiers_with_defaults.items():
            if identifier in mappings:
                resolved_identifiers[identifier] = cast(str, mappings[identifier])
            elif default_value is not None:
                resolved_identifiers[identifier] = default_value
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
            return _json_loads(new_specs_txt)
        except KeyError as e:
            raise IdentifierSubstitutionError(
                name=e.args[0], substitutions=self._substitutions
            ) from e
