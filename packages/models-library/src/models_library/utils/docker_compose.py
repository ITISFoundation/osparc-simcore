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


def create_text_template(
    compose_service_spec: dict[str, Any] | str, *, upgrade: bool
) -> TextTemplate:
    # convert
    if isinstance(compose_service_spec, dict):
        service_spec_str: str = yaml.safe_dump(compose_service_spec)
    else:
        service_spec_str = compose_service_spec

    if upgrade:  # legacy
        service_spec_str = substitute_all_legacy_identifiers(service_spec_str)

    # template
    template = TextTemplate(service_spec_str)
    assert template.is_valid()

    return template
