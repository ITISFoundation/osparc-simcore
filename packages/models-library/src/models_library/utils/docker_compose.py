from typing import Any

import yaml
from models_library.utils.string_substitution import (
    SubstitutionsDict,
    TextTemplate,
    substitute_all_legacy_identifiers,
)

from .string_substitution import SubstitutionsDict, TextTemplate

# Notes on below env var names:
# - SIMCORE_REGISTRY will be replaced by the url of the simcore docker registry
# deployed inside the platform
# - SERVICE_VERSION will be replaced by the version of the service
# to which this compos spec is attached
# Example usage in docker compose:
#   image: ${SIMCORE_REGISTRY}/${DOCKER_IMAGE_NAME}-dynamic-sidecar-compose-spec:${SERVICE_VERSION}

MATCH_SERVICE_VERSION = "${SERVICE_VERSION}"
MATCH_SIMCORE_REGISTRY = "${SIMCORE_REGISTRY}"
MATCH_IMAGE_START = f"{MATCH_SIMCORE_REGISTRY}/"
MATCH_IMAGE_END = f":{MATCH_SERVICE_VERSION}"


def replace_env_vars_in_compose_spec(
    service_spec: "ComposeSpecLabelDict",
    *,
    replace_simcore_registry: str,
    replace_service_version: str,
) -> str:
    """
    replaces all special env vars inside docker-compose spec
    returns a stringified version
    """

    content: str = yaml.safe_dump(service_spec)

    template = TextTemplate(content)
    substitutions = SubstitutionsDict(
        {
            "SERVICE_VERSION": replace_service_version,
            "SIMCORE_REGISTRY": replace_simcore_registry,
        }
    )
    resolved_content: str = template.safe_substitute(substitutions)

    return resolved_content


class SpecsEnvironmentsResolver:
    # TODO: this does not belongs here! knows nothing about docker so far!

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

    def set_substitutions(self, environs: dict[str, str | int]) -> SubstitutionsDict:
        # FIXME: test values different from str and int!!! Note that secrets can be Any!
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
        new_specs: dict = yaml.safe_load(new_specs_txt)
        return new_specs
