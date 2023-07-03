# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

import json
import sys
from pathlib import Path
from textwrap import dedent

import pytest
from models_library.utils.string_substitution import (
    SubstitutionsDict,
    TextTemplate,
    substitute_all_legacy_identifiers,
    upgrade_identifier,
)
from pytest_simcore.helpers.utils_envs import load_dotenv


@pytest.mark.parametrize(
    "legacy,expected",
    [
        (
            "%%container_name.sym-server%%",
            "OSPARC_VARIABLE_CONTAINER_NAME_SYM_SERVER",
        ),
        (
            "%service_uuid%",
            "OSPARC_VARIABLE_SERVICE_UUID",
        ),
        (
            "$SERVICE_VERSION",
            "OSPARC_VARIABLE_SERVICE_VERSION",
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
            image: ${SIMCORE_REGISTRY}/simcore/services/dynamic/dy-vendor-service:${SERVICE_VERSION}
            environment:
                # legacy examples
                - SYM_SERVER_HOSTNAME=%%container_name.sym-server%%
                - APP_HOSTNAME=%%container_name.dsistudio-app%%
                - APP_HOSTNAME=some-prefix_%service_uuid%
                - MY_LICENSE_FILE=${OSPARC_VARIABLE_VENDOR_SECRET_LICENSE_FILE}
                - MY_PRODUCT=$OSPARC_VARIABLE_CURRENT_PRODUCT
                - MY_EMAIL=$OSPARC_VARIABLE_USER_EMAIL
                - AS_VOILA=1
                - DISPLAY1=$${KEEP_SINCE_IT_USES_DOLLAR_ESCAPE_SIGN}
                - DISPLAY2=${KEEP_SINCE_IT_WAS_EXCLUDED_FROM_SUBSTITUTIONS}
    containers-allowed-outgoing-permit-list:
        s4l-core:
            - hostname: $OSPARC_VARIABLE_VENDOR_SECRET_LICENSE_SERVER_HOST
              tcp_ports: [$OSPARC_VARIABLE_VENDOR_SECRET_LICENSE_SERVER_PRIMARY_PORT, $OSPARC_VARIABLE_VENDOR_SECRET_LICENSE_SERVER_SECONDARY_PORT]
              dns_resolver:
                  address: $OSPARC_VARIABLE_VENDOR_SECRET_LICENSE_DNS_RESOLVER_IP
                  port: $OSPARC_VARIABLE_VENDOR_SECRET_LICENSE_DNS_RESOLVER_PORT
    containers-allowed-outgoing-internet:
        - s4l-core-stream
    """

    stringified_config = substitute_all_legacy_identifiers(stringified_config)

    template = TextTemplate(stringified_config)

    assert template.is_valid()
    identifiers = template.get_identifiers()
    assert identifiers == [
        "SIMCORE_REGISTRY",
        "SERVICE_VERSION",
        # NOTE: these identifier names were upgraded from legacy
        "OSPARC_VARIABLE_CONTAINER_NAME_SYM_SERVER",
        "OSPARC_VARIABLE_CONTAINER_NAME_DSISTUDIO_APP",
        "OSPARC_VARIABLE_SERVICE_UUID",
        # -----
        "OSPARC_VARIABLE_VENDOR_SECRET_LICENSE_FILE",
        "OSPARC_VARIABLE_CURRENT_PRODUCT",
        "OSPARC_VARIABLE_USER_EMAIL",
        "KEEP_SINCE_IT_WAS_EXCLUDED_FROM_SUBSTITUTIONS",
        "OSPARC_VARIABLE_VENDOR_SECRET_LICENSE_SERVER_HOST",
        "OSPARC_VARIABLE_VENDOR_SECRET_LICENSE_SERVER_PRIMARY_PORT",
        "OSPARC_VARIABLE_VENDOR_SECRET_LICENSE_SERVER_SECONDARY_PORT",
        "OSPARC_VARIABLE_VENDOR_SECRET_LICENSE_DNS_RESOLVER_IP",
        "OSPARC_VARIABLE_VENDOR_SECRET_LICENSE_DNS_RESOLVER_PORT",
    ]

    # prepare substitutions map {id: value, ...}
    exclude = {"KEEP_SINCE_IT_WAS_EXCLUDED_FROM_SUBSTITUTIONS"}
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
            image: VALUE/simcore/services/dynamic/dy-vendor-service:VALUE
            environment:
                # legacy examples
                - SYM_SERVER_HOSTNAME=VALUE
                - APP_HOSTNAME=VALUE
                - APP_HOSTNAME=some-prefix_VALUE
                - MY_LICENSE_FILE=VALUE
                - MY_PRODUCT=VALUE
                - MY_EMAIL=VALUE
                - AS_VOILA=1
                - DISPLAY1=${KEEP_SINCE_IT_USES_DOLLAR_ESCAPE_SIGN}
                - DISPLAY2=${KEEP_SINCE_IT_WAS_EXCLUDED_FROM_SUBSTITUTIONS}
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
    "OSPARC_VARIABLE_CONTAINER_NAME_DSISTUDIO_APP",
    "OSPARC_VARIABLE_CONTAINER_NAME_FSL_APP",
    "OSPARC_VARIABLE_CONTAINER_NAME_ISEG_APP",
    "OSPARC_VARIABLE_CONTAINER_NAME_S4L_CORE",
    "OSPARC_VARIABLE_CONTAINER_NAME_SCT_LABEL_UTILS_APP",
    "OSPARC_VARIABLE_CONTAINER_NAME_SPINAL_CORD_TOOLBOX_APP",
    "OSPARC_VARIABLE_CONTAINER_NAME_SYM_SERVER",
    "OSPARC_VARIABLE_SERVICE_UUID",
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

    template = TextTemplate(meta_str)
    assert template.is_valid()

    found = template.get_identifiers()
    if found:
        assert all(
            identifier in KNOWN_IDENTIFIERS for identifier in found
        ), f"some identifiers in {found} are new and therefore potentially unsupported"


def test_template_substitution_on_envfiles():
    envfile_template = dedent(
        """
    x=$VALUE1
    y=$VALUE2
    """
    )
    template = TextTemplate(envfile_template)
    assert set(template.get_identifiers()) == {"VALUE1", "VALUE2"}

    # NOTE how it casts string to to int
    assert template.substitute({"VALUE1": "3", "VALUE2": 3}) == dedent(
        """
    x=3
    y=3
    """
    )

    # NOTE does not cast if it is in a container
    assert template.substitute({"VALUE1": ["3", "4"], "VALUE2": [3, 4]}) == dedent(
        """
    x=['3', '4']
    y=[3, 4]
    """
    )

    # deserialized AFTER substitution in envfile template
    deserialize = load_dotenv(template.substitute({"VALUE1": "3", "VALUE2": 3}))
    assert deserialize == {
        "x": "3",
        "y": "3",
    }

    deserialize = load_dotenv(
        template.substitute({"VALUE1": ["3", "4"], "VALUE2": [3, 4]})
    )
    assert deserialize == {
        "x": "['3', '4']",
        "y": "[3, 4]",
    }


def test_template_substitution_on_jsondumps():
    # NOTE: compare with test_template_substitution_on_envfiles

    json_template = {"x": "$VALUE1", "y": "$VALUE2"}
    json_dumps_template = json.dumps(json_template)  # LIKE image labels!

    # NOTE: that here we are enforcing the values to be strings!
    assert '{"x": "$VALUE1", "y": "$VALUE2"}' == json_dumps_template

    template = TextTemplate(json_dumps_template)
    assert set(template.get_identifiers()) == {"VALUE1", "VALUE2"}

    # NOTE how it casts string to str
    deserialized = json.loads(template.substitute({"VALUE1": "3", "VALUE2": 3}))

    assert deserialized == {
        "x": "3",
        "y": "3",  # <--- NOTE cast to str!
    }

    # NOTE does not cast if it is in a container
    deserialized = json.loads(
        template.substitute({"VALUE1": ["3", "4"], "VALUE2": [3, 4]})
    )

    assert deserialized == {
        "x": "['3', '4']",
        "y": "[3, 4]",
    }
