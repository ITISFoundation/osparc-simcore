"""
    Helper functions to create models from mother modules
"""
import uuid
from datetime import datetime
from functools import lru_cache

from ..models.domain.projects import (
    InputTypes,
    NewProjectIn,
    Node,
    SimCoreFileLink,
    StudyUI,
)
from ..models.schemas.files import File
from ..models.schemas.jobs import Job, JobInputs
from ..models.schemas.solvers import Solver

# UTILS ------
_BASE_UUID = uuid.UUID("231e13db-6bc6-4f64-ba56-2ee2c73b9f09")


@lru_cache()
def compose_uuid_from(*values) -> str:
    composition = "/".join(map(str, values))
    new_uuid = uuid.uuid5(_BASE_UUID, composition)
    return str(new_uuid)


def format_dt(snapshot: datetime) -> str:
    return "{}Z".format(snapshot.isoformat(timespec="milliseconds"))


def now_str() -> str:
    return format_dt(datetime.utcnow())


# CREATE HELPERS --------


def create_project_model_for_job(
    solver: Solver, job: Job, inputs: JobInputs
) -> NewProjectIn:
    """
    Creates a project for a solver's job
    """
    project_id = job.id
    solver_id = compose_uuid_from(project_id, solver.id)

    # solver

    # map Job inputs with solveri nputs
    # TODO: ArgumentType -> InputTypes dispatcher

    solver_inputs = {}
    for input_name, value in inputs.values.items():
        assert InputTypes
        # TODO: assert type(value) in InputTypes

        if isinstance(value, File):
            solver_inputs[input_name] = SimCoreFileLink(
                path=f"api/{value.id}/{value.filename}", label=value.filename
            )
        else:
            solver_inputs[input_name] = value

    solver_service = Node(
        key=solver.id,
        version=solver.version,
        label=solver.title,
        inputs=solver_inputs,
    )

    # Ensembles project model so it can be used as input for create_project
    new_project = NewProjectIn(
        uuid=project_id,
        name=f"API Job {job.name}",
        description=f"Study associated to solver job {job.name}",
        thumbnail="https://placeimg.com/171/96/tech/grayscale/?0.jpg",
        workbench={solver_id: solver_service},
        ui=StudyUI(
            workbench={
                solver_id: {"position": {"x": 633, "y": 229}},
            }
        ),
        # FIXME: these should be unnecessary
        prjOwner="api-placeholder@osparc.io",
        creationDate=now_str(),
        lastChangeDate=now_str(),
        accessRights={},
    )

    return new_project
