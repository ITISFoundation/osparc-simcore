from simcore_service_webserver.projects.projects_schemas import (
    ProjectCreate,
    ProjectGet,
)


def test_convert_db_to_Get():
    ProjectGet.parse_obj(None)
    ProjectCreate.parse_obj(None)
