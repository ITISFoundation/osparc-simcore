from typing import Any, TypeAlias, cast

import yaml
from pydantic import StrictBool, StrictFloat, StrictInt

from .string_substitution import (
    SubstitutionsDict,
    TextTemplate,
    substitute_all_legacy_identifiers,
)

# This constraint on substitution values is to avoid
# deserialization issues on the TextTemplate substitution!
SubstitutionValue: TypeAlias = StrictBool | StrictInt | StrictFloat | str


class SpecsSubstitutionsResolver:
    """
    Resolve specs dict by substituting identifiers

    'specs' is defined here as dict[str, Any]. E.g. a docker-compose.yml loaded as a dict are 'specs'.

    """

    def __init__(self, specs: dict[str, Any], upgrade: bool):
        self._template = self._create_text_template(specs, upgrade=upgrade)
        self._substitutions: SubstitutionsDict = SubstitutionsDict()

    @classmethod
    def _create_text_template(
        cls, specs: dict[str, Any], *, upgrade: bool
    ) -> TextTemplate:
        # convert to yaml (less symbols as in json)
        service_spec_str: str = yaml.safe_dump(specs)

        if upgrade:  # legacy
            service_spec_str = substitute_all_legacy_identifiers(service_spec_str)

        # template
        template = TextTemplate(service_spec_str)
        assert template.is_valid()  # nosec

        return template

    def get_identifiers(self) -> list[str]:
        """lists identifiers in specs in order of apperance. Can have repetitions"""
        return self._template.get_identifiers()

    def get_replaced(self) -> set[str]:
        return self._substitutions.used

    @property
    def substitutions(self):
        return self._substitutions

    def set_substitutions(
        self, environs: dict[str, SubstitutionValue]
    ) -> SubstitutionsDict:
        """NOTE: ONLY targets identifiers declared in the specs"""
        identifiers_needed = self.get_identifiers()

        # picks only needed for substitution
        self._substitutions = SubstitutionsDict(
            {
                identifier: environs[identifier]
                for identifier in identifiers_needed
                if identifier in environs
            }
        )
        return self._substitutions

    def run(self) -> dict[str, Any]:
        new_specs_txt: str = self._template.safe_substitute(self._substitutions)
        new_specs = yaml.safe_load(new_specs_txt)
        return cast(dict[str, Any], new_specs)
