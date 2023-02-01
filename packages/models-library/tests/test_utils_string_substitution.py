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
                - APP_HOSTNAME=some-prefix_%service_uuid%
                - SPEAG_LICENSE_FILE=${OSPARC_ENVIRONMENT_SPEAG_LICENSE_FILE}
                - MY_PRODUCT=$OSPARC_ENVIRONMENT_CURRENT_PRODUCT
                - MY_EMAIL=$OSPARC_ENVIRONMENT_USER_EMAIL
                - S4L_LITE_PRODUCT=yes
                - AS_VOILA=1
                - DISPLAY1=$${KEEP_DISPLAY}
                - DISPLAY2=${SKIP_DISPLAY}
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
    identifiers = template.get_identifiers()
    assert identifiers == [
        "SIMCORE_REGISTRY",
        "SERVICE_VERSION",
        # NOTE: these identifier names were upgraded from legacy
        "OSPARC_ENVIRONMENT_CONTAINER_NAME_SYM_SERVER",
        "OSPARC_ENVIRONMENT_CONTAINER_NAME_DSISTUDIO_APP",
        "OSPARC_ENVIRONMENT_SERVICE_UUID",
        # -----
        "OSPARC_ENVIRONMENT_SPEAG_LICENSE_FILE",
        "OSPARC_ENVIRONMENT_CURRENT_PRODUCT",
        "OSPARC_ENVIRONMENT_USER_EMAIL",
        "SKIP_DISPLAY",
        "OSPARC_ENVIRONMENT_LICENSE_SERVER_HOST",
        "OSPARC_ENVIRONMENT_LICENSE_SERVER_PRIMARY_PORT",
        "OSPARC_ENVIRONMENT_LICENSE_SERVER_SECONDARY_PORT",
        "OSPARC_ENVIRONMENT_LICENSE_DNS_RESOLVER_IP",
        "OSPARC_ENVIRONMENT_LICENSE_DNS_RESOLVER_PORT",
    ]

    # prepare substitutions map {id: value, ...}
    exclude = {"SKIP_DISPLAY"}
    substitutions = SubstitutionsDict(
        {idr: "VALUE" for idr in identifiers if idr not in exclude}
    )

    # uses safe because we exclude some identifiers from substitution
    resolved_stringified_config = template.safe_substitute(substitutions)

    # all entries in the substitutions list were used
    assert not substitutions.unused
    assert substitutions.used == set(substitutions.keys())

    # let's check how "VALUE"
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
                - APP_HOSTNAME=some-prefix_VALUE
                - SPEAG_LICENSE_FILE=VALUE
                - MY_PRODUCT=VALUE
                - MY_EMAIL=VALUE
                - S4L_LITE_PRODUCT=yes
                - AS_VOILA=1
                - DISPLAY1=${KEEP_DISPLAY}
                - DISPLAY2=${SKIP_DISPLAY}
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


CURRENT_DIR = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent
TEST_DATA_FOLDER = CURRENT_DIR / "data"


# Some fo the supported identifiers
KNOWN_IDENTIFIERS = {
    "DISPLAY",  # NOTE: this might be a mistake!
    "OSPARC_ENVIRONMENT_CONTAINER_NAME_DSISTUDIO_APP",
    "OSPARC_ENVIRONMENT_CONTAINER_NAME_FSL_APP",
    "OSPARC_ENVIRONMENT_CONTAINER_NAME_ISEG_APP",
    "OSPARC_ENVIRONMENT_CONTAINER_NAME_S4L_CORE",
    "OSPARC_ENVIRONMENT_CONTAINER_NAME_SCT_LABEL_UTILS_APP",
    "OSPARC_ENVIRONMENT_CONTAINER_NAME_SPINAL_CORD_TOOLBOX_APP",
    "OSPARC_ENVIRONMENT_CONTAINER_NAME_SYM_SERVER",
    "OSPARC_ENVIRONMENT_SERVICE_UUID",
    "SERVICE_VERSION",
    "SIMCORE_REGISTRY",
}


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
