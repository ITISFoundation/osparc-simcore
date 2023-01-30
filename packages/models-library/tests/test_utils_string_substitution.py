# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from models_library.utils.string_substitution import SubstitutionsDict, TemplateExtended


def test_string_template_extended():

    template = TemplateExtended(
        """
  dy-static-file-server-dynamic-sidecar-compose-spec:
    init: true
    image: ${SIMCORE_REGISTRY}/simcore/services/dynamic/dy-static-file-server-dynamic-sidecar-compose-spec:${SERVICE_VERSION}
    environment:
      - MOCK_VALUE=$${WITH_ESPAPED_DOLLAR}
      # app specific
      - TZ=Europe/Zurich
      # app specific BUT from a framework configuration
      - MY_USER_ROLE=${OSPARC_USER_ROLE}
      - MY_EMAIL=${OSPARC_USER_EMAIL}
      - MY_PRODUCT_NAME=$OSPARC_PRODUCT_NAME
      - MY_API_KEY=PREFIX_$OSPARC_USER_API_KEY
      - MY_API_SECRET=${OSPARC_USER_API_SECRET}_AND_SUFFIX
      - SPEAG_LICENSE_FILE=$OSPARC_USER_SPEAG_LICENSE_FILE
      - HASHED_PASSWORD=$UNDEFINED_IN_OSPARC
      - REPEATED=$OSPARC_USER_SPEAG_LICENSE_FILE
"""
    )

    assert template.is_valid()
    assert template.get_identifiers() == [
        "SIMCORE_REGISTRY",
        "SERVICE_VERSION",
        "OSPARC_USER_ROLE",
        "OSPARC_USER_EMAIL",
        "OSPARC_PRODUCT_NAME",
        "OSPARC_USER_API_KEY",
        "OSPARC_USER_API_SECRET",
        "OSPARC_USER_SPEAG_LICENSE_FILE",  # repeated only appears once!
        "UNDEFINED_IN_OSPARC",
    ]

    substitutions = SubstitutionsDict(
        {
            "OSPARC_USER_API_KEY": "123456",
            "OSPARC_USER_EMAIL": "user@email.com",
            "SERVICE_VERSION": "1.2.3",
            "SOME_OTHER_KEY": False,
        }
    )

    result: str = template.safe_substitute(substitutions)

    assert substitutions.used == {
        "OSPARC_USER_EMAIL",
        "OSPARC_USER_API_KEY",
        "SERVICE_VERSION",
    }
    assert substitutions.unused == {"SOME_OTHER_KEY"}

    assert (
        result
        == """
  dy-static-file-server-dynamic-sidecar-compose-spec:
    init: true
    image: ${SIMCORE_REGISTRY}/simcore/services/dynamic/dy-static-file-server-dynamic-sidecar-compose-spec:1.2.3
    environment:
      - MOCK_VALUE=${WITH_ESPAPED_DOLLAR}
      # app specific
      - TZ=Europe/Zurich
      # app specific BUT from a framework configuration
      - MY_USER_ROLE=${OSPARC_USER_ROLE}
      - MY_EMAIL=user@email.com
      - MY_PRODUCT_NAME=$OSPARC_PRODUCT_NAME
      - MY_API_KEY=PREFIX_123456
      - MY_API_SECRET=${OSPARC_USER_API_SECRET}_AND_SUFFIX
      - SPEAG_LICENSE_FILE=$OSPARC_USER_SPEAG_LICENSE_FILE
      - HASHED_PASSWORD=$UNDEFINED_IN_OSPARC
      - REPEATED=$OSPARC_USER_SPEAG_LICENSE_FILE
"""
    )
