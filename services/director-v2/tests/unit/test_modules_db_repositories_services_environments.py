from models_library.osparc_variable_identifier import OsparcVariableIdentifier
from pydantic import TypeAdapter
from simcore_postgres_database.models.services_environments import VENDOR_SECRET_PREFIX


def test_vendor_secret_names_are_osparc_environments():
    # NOTE that this is tested here because the constants are defined in
    # packages simcore_postgres_database and models_library which are indenpendent
    assert VENDOR_SECRET_PREFIX.endswith("_")

    TypeAdapter(OsparcVariableIdentifier).validate_python(f"${VENDOR_SECRET_PREFIX}FAKE_SECRET")
