from models_library.service_settings_labels import OEnvSubstitutionStr
from pydantic import parse_obj_as
from simcore_postgres_database.models.services_environments import VENDOR_SECRET_PREFIX


def test_vendor_secret_names_are_osparc_environments():
    # NOTE that this is tested here because the constants are defined in
    # packages simcore_postgres_database and models_library which are indenpendent
    assert VENDOR_SECRET_PREFIX.endswith("_")

    parse_obj_as(OEnvSubstitutionStr, f"${VENDOR_SECRET_PREFIX}FAKE_SECRET")
