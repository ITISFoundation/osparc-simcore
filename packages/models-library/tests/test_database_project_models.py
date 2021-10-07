from models_library.database_project_models import ProjectAtDB, ProjectFromCsv
from models_library.utils.database_models_factory import (
    create_pydantic_model_from_sa_table,
)
from simcore_postgres_database.models.projects import projects as projects_table


def tests_project_from_csv_file():
    ...
    # TODO:


def test_project_models_in_sync_with_tables():

    ProjectTableModel = create_pydantic_model_from_sa_table(projects_table)

    assert set(ProjectAtDB.__fields__.keys()) == set(
        ProjectTableModel.__fields__.keys()
    )
    assert set(ProjectFromCsv.__fields__.keys()) == set(
        ProjectTableModel.__fields__.keys()
    )

    # TODO: use above to produce a static table

    # compare ProjectAtDB with ProjectTableModel
