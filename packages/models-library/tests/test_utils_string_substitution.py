# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

import sys
from pathlib import Path

import pytest
from models_library.utils.string_substitution import (
    SubstitutionsDict,
    TemplateText,
    substitute_all_legacy_identifiers,
    upgrade_identifier,
)


@pytest.mark.testit
@pytest.mark.parametrize(
    "legacy,expected",
    [
        (
            "%%container_name.sym-server%%",
            "OSPARC_ENVIRONMENT_CONTAINER_NAME_SYM_SERVER",
        ),
        (
            "%service_uuid%",
            "OSPARC_ENVIRONMENT_SERVICE_UUID",
        ),
    ],
)
def test_upgrade_identifiers(legacy: str, expected: str):
    assert upgrade_identifier(legacy) == expected


@pytest.mark.testit
def test_substitution_with_new_and_legacy_identifiers():

    stringified_config = """
    compose_spec:
        service-one:
            init: true
            image: ${SIMCORE_REGISTRY}/simcore/services/dynamic/dy-static-file-server-dynamic-sidecar-compose-spec:${SERVICE_VERSION}
            environment:
                # legacy examples
                - SYM_SERVER_HOSTNAME=%%container_name.sym-server%%
                - APP_HOSTNAME=%%container_name.dsistudio-app%%
                - APP_HOSTNAME=bio-formats-app_%service_uuid%
                - SPEAG_LICENSE_FILE=${OSPARC_ENVIRONMENT_SPEAG_LICENSE_FILE}
                - MY_PRODUCT=$OSPARC_ENVIRONMENT_CURRENT_PRODUCT
                - MY_EMAIL=$OSPARC_ENVIRONMENT_USER_EMAIL
                - S4L_LITE_PRODUCT=yes
                - AS_VOILA=1
    containers-allowed-outgoing-permit-list:
        s4l-core:
            - hostname: $OSPARC_ENVIRONMENT_LICENSE_SERVER_HOST
              tcp_ports: [$OSPARC_ENVIRONMENT_LICENSE_SERVER_PRIMARY_PORT, $OSPARC_ENVIRONMENT_LICENSE_SERVER_SECONDARY_PORT]
              dns_resolver:
                  address: $OSPARC_ENVIRONMENT_LICENSE_DNS_RESOLVER_IP
                  port: $OSPARC_ENVIRONMENT_LICENSE_DNS_RESOLVER_PORT
    containers-allowed-outgoing-internet:
        - s4l-core-stream
    """

    stringified_config = substitute_all_legacy_identifiers(stringified_config)

    template = TemplateText(stringified_config)

    assert template.is_valid()
    assert template.get_identifiers() == [
        "SIMCORE_REGISTRY",
        "SERVICE_VERSION",
        # upgraded
        "OSPARC_ENVIRONMENT_CONTAINER_NAME_SYM_SERVER",
        "OSPARC_ENVIRONMENT_CONTAINER_NAME_DSISTUDIO_APP",
        "OSPARC_ENVIRONMENT_SERVICE_UUID",
        # --
        "OSPARC_ENVIRONMENT_SPEAG_LICENSE_FILE",
        "OSPARC_ENVIRONMENT_CURRENT_PRODUCT",
        "OSPARC_ENVIRONMENT_USER_EMAIL",
        "OSPARC_ENVIRONMENT_LICENSE_SERVER_HOST",
        "OSPARC_ENVIRONMENT_LICENSE_SERVER_PRIMARY_PORT",
        "OSPARC_ENVIRONMENT_LICENSE_SERVER_SECONDARY_PORT",
        "OSPARC_ENVIRONMENT_LICENSE_DNS_RESOLVER_IP",
        "OSPARC_ENVIRONMENT_LICENSE_DNS_RESOLVER_PORT",
    ]

    substitutions = SubstitutionsDict(
        {idr: "VALUE" for idr in template.get_identifiers()}
    )

    resolved_stringified_config = template.substitute(substitutions)

    assert not substitutions.unused
    assert substitutions.used == set(template.get_identifiers())

    assert (
        resolved_stringified_config
        == """
    compose_spec:
        service-one:
            init: true
            image: VALUE/simcore/services/dynamic/dy-static-file-server-dynamic-sidecar-compose-spec:VALUE
            environment:
                # legacy examples
                - SYM_SERVER_HOSTNAME=VALUE
                - APP_HOSTNAME=VALUE
                - APP_HOSTNAME=bio-formats-app_VALUE
                - SPEAG_LICENSE_FILE=VALUE
                - MY_PRODUCT=VALUE
                - MY_EMAIL=VALUE
                - S4L_LITE_PRODUCT=yes
                - AS_VOILA=1
    containers-allowed-outgoing-permit-list:
        s4l-core:
            - hostname: VALUE
              tcp_ports: [VALUE, VALUE]
              dns_resolver:
                  address: VALUE
                  port: VALUE
    containers-allowed-outgoing-internet:
        - s4l-core-stream
    """
    )

    # template = TemplateString(stringified_config)

    # assert template.get_identifiers() == [
    #     "SIMCORE_REGISTRY",
    #     "SERVICE_VERSION",
    #     "OSPARC_SERVICES_SPEAG_LICENSE_FILE",
    # ]

    # # somewhere we define published environments

    # def factory_request_api_key(user_id: int):
    #     def request():
    #         return "TOKEN_{user_id}"

    #     return request

    # # replicates replace_env_vars_in_compose_spec

    # # Substitutions created provided a given context (user, product, service, organization, ...)
    # substitutions = SubstitutionsDict(
    #     {
    #         "SERVICE_VERSION": "1.2.3",
    #         "SIMCORE_REGISTRY": "registry.com",
    #         "API_KEYS": factory_request_api_key(user_id=1)(),
    #     }
    # )


CURRENT_DIR = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent
TEST_DATA_FOLDER = CURRENT_DIR / "data"


# supported identifiers
KNOWN_IDENTIFIERS = {"DISPLAY", "SERVICE_VERSION", "SIMCORE_REGISTRY"}


@pytest.mark.testit
@pytest.mark.diagnostics
@pytest.mark.parametrize(
    "metadata_path",
    TEST_DATA_FOLDER.rglob("metadata*.json"),
    ids=lambda p: f"{p.parent.name}/{p.name}",
)
def test_substitution_against_service_metadata_configs(metadata_path: Path):

    meta_str = metadata_path.read_text()
    meta_str = substitute_all_legacy_identifiers(meta_str)

    template = TemplateText(meta_str)
    assert template.is_valid()

    found = template.get_identifiers()
    if found:
        assert all(
            identifier in KNOWN_IDENTIFIERS for identifier in found
        ), f"some identifiers in {found} are new and therefore potentially unsupported"
