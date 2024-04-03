from fastapi import HTTPException, status
from models_library.api_schemas_webserver.projects import ProjectGet


def raise_if_job_not_associated_with_solver(
    expected_project_name: str, project: ProjectGet
) -> None:
    if expected_project_name != project.name:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid input data for job {project.uuid}",
        )
