from models_library.service_settings_labels import OEnvSubstitutionStr
from pydantic import parse_obj_as
from simcore_postgres_database.models.services_environments import VENDOR_SECRET_PREFIX


def test_vendor_secret_names_are_osparc_environments():
    # NOTE that this test
    assert VENDOR_SECRET_PREFIX.endswith("_")

    parse_obj_as(OEnvSubstitutionStr, VENDOR_SECRET_PREFIX + "fake_secret")
