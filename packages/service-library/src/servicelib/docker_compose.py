import yaml

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
    service_spec: "ComposeSpecLabel",
    *,
    replace_simcore_registry: str,
    replace_service_version: str,
) -> str:
    """
    replaces all special env vars inside docker-compose spec
    returns a stringified version
    """

    stringified_service_spec = yaml.safe_dump(service_spec)

    # NOTE: could not use `string.Template` here because the test will
    # fail since `${DISPLAY}` cannot be replaced, and we do not want
    # it to be replaced at this time. If this method is changed
    # the test suite should always pass without changes.
    stringified_service_spec = stringified_service_spec.replace(
        MATCH_SIMCORE_REGISTRY, replace_simcore_registry
    )
    stringified_service_spec = stringified_service_spec.replace(
        MATCH_SERVICE_VERSION, replace_service_version
    )
    return stringified_service_spec
