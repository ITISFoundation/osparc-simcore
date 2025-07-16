def patch_osparc_variable_identifier() -> None:
    # NOTE: `$$$${` is only required when validating on systems that have
    # an updated version of docker
    # when running `ooil compose-spec` this will fail
    # since it requires `$$$${` of env vars sinstead of `$${`
    # This is a followup to https://github.com/ITISFoundation/osparc-simcore/pull/8085

    from models_library.osparc_variable_identifier import OsparcVariableIdentifier
    from models_library.utils.string_substitution import OSPARC_IDENTIFIER_PREFIX

    OsparcVariableIdentifier.pattern = (
        rf"^\${{1,4}}(?:\{{)?{OSPARC_IDENTIFIER_PREFIX}[A-Za-z0-9_]+(?:\}})?(:-.+)?$"
    )
