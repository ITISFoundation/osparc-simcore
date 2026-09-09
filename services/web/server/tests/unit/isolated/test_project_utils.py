from models_library.projects import ProjectType as ml_project_type
from simcore_postgres_database.models.projects import ProjectType as pg_project_type


def test_project_type_in_models_package_same_as_in_postgres_database_package():
    # pylint: disable=no-member
    assert ml_project_type.__members__.keys() == pg_project_type.__members__.keys(), (
        f"The enum in models_library package and postgres package shall have the same values. models_pck: {ml_project_type.__members__}, postgres_pck: {pg_project_type.__members__}"
    )
