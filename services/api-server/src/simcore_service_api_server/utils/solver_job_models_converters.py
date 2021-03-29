"""
    Helper functions to create and transform models
"""
import uuid
from datetime import datetime
from functools import lru_cache
from mimetypes import guess_type
from typing import Callable, Dict

from models_library.projects_nodes import InputID, InputTypes

from ..models.domain.projects import (
    InputTypes,
    NewProjectIn,
    Node,
    Project,
    SimCoreFileLink,
    StudyUI,
)
from ..models.schemas.files import File
from ..models.schemas.jobs import ArgumentType, Job, JobInputs, JobStatus, TaskStates
from ..models.schemas.solvers import Solver, SolverKeyId, VersionStr
from ..modules.director_v2 import ComputationTaskOut

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


def get_args(annotation):
    # TODO: py3.8 use typings.get_args
    return annotation.__args__


# TRANSFORMATIONS --------------
#
# - creates a model in one API composing models in others
#


def create_node_inputs_from_job_inputs(inputs: JobInputs) -> Dict[InputID, InputTypes]:

    # map Job inputs with solver inputs
    # TODO: ArgumentType -> InputTypes dispatcher

    node_inputs: Dict[InputID, InputTypes] = {}
    for name, value in inputs.values.items():

        # TODO: py3.8 use typings.get_args
        assert isinstance(value, get_args(ArgumentType))

        if isinstance(value, File):
            # FIXME: ensure this aligns with storage policy
            node_inputs[name] = SimCoreFileLink(
                path=f"api/{value.id}/{value.filename}", label=value.filename
            )
        else:
            node_inputs[name] = value

    # TODO: validate Inputs??

    return node_inputs


def create_job_inputs_from_node_inputs(inputs: Dict[InputID, InputTypes]) -> JobInputs:
    """Reverse  from create_node_inputs_from_job_inputs

    raises ValidationError
    """
    input_values: Dict[str, ArgumentType] = {}
    for name, value in inputs.items():

        assert isinstance(name, InputID)
        assert isinstance(value, get_args(InputTypes))

        if isinstance(value, SimCoreFileLink):
            # FIXME: ensure this aligns with storage policy
            _api, file_id, filename = value.path.split("/")
            assert _api == "api"
            input_values[name] = File(
                id=file_id,
                filename=filename,
                content_type=guess_type(filename),
                checksum=value.e_tag,
            )
        else:
            input_values[name] = value

    job_inputs = JobInputs(values=input_values)  # raises ValidationError
    return job_inputs


def get_node_id(project_id, solver_id) -> str:
    # By clumsy design, the webserver needs a global uuid,
    # so we decieded to compose as this
    return compose_uuid_from(project_id, solver_id)


def create_project_from_job(
    solver: Solver, job: Job, inputs: JobInputs
) -> NewProjectIn:
    """
    Creates a project for a solver's job

    Returns model used in the body of create_project at the web-server API

    In reality, we also need solvers and inputs to produce
    the project, but the name of the function is intended
    to stress the one-to-one equivalence between a project
    (model at web-server API) and a job (model at api-server API)


    raises ValidationError
    """
    project_id = job.id
    solver_id = get_node_id(project_id, solver.id)

    # solver

    # map Job inputs with solveri nputs
    # TODO: ArgumentType -> InputTypes dispatcher and reversed
    solver_inputs: Dict[InputID, InputTypes] = create_node_inputs_from_job_inputs(
        inputs
    )

    solver_service = Node(
        key=solver.id,
        version=solver.version,
        label=solver.title,
        inputs=solver_inputs,
    )

    # Ensembles project model so it can be used as input for create_project
    job_info = job.json(
        include={"id", "name", "inputs_checksum", "created_at"}, indent=2
    )

    create_project_body = NewProjectIn(
        uuid=project_id,
        name=job.name,  # NOTE: this IS an identifier as well. MUST NOT be changed in the case of project APIs!
        description=f"Study associated to solver job:\n{job_info}",
        thumbnail="https://2xx2gy2ovf3r21jclkjio3x8-wpengine.netdna-ssl.com/wp-content/uploads/2018/12/API-Examples.jpg",  # https://placeimg.com/171/96/tech/grayscale/?0.jpg",
        workbench={solver_id: solver_service},
        ui=StudyUI(
            workbench={
                solver_id: {"position": {"x": 633, "y": 229}},
            },
            slideshow={},
            currentNodeId=solver_id,
        ),
        ## hidden=True,  # FIXME: add
        # FIXME: these should be unnecessary
        prjOwner="api-placeholder@osparc.io",
        creationDate=now_str(),
        lastChangeDate=now_str(),
        accessRights={},
        dev={},
    )

    return create_project_body


# TODO:
# def create_job_from_data(project, computation_task):
#    pass


def copy_n_update_urls(
    job: Job, url_for: Callable, solver_key: SolverKeyId, version: VersionStr
):
    return job.copy(
        update={
            "url": url_for(
                "get_job", solver_key=solver_key, version=version, job_id=job.id
            ),
            "runner_url": url_for(
                "get_solver_release",
                solver_key=solver_key,
                version=version,
            ),
            "outputs_url": url_for(
                "get_job_outputs",
                solver_key=solver_key,
                version=version,
                job_id=job.id,
            ),
        }
    )


def create_job_from_project(
    solver_key: SolverKeyId,
    version: VersionStr,
    project: Project,
    url_for: Callable,
) -> Job:
    """
    Given a project, creates a job

    Complementary from create_project_from_job
    raise ValidationError
    """
    assert len(project.workbench) == 1

    node_id = list(project.workbench.keys())[0]
    solver_node: Node = project.workbench[node_id]

    job_inputs: JobInputs = create_job_inputs_from_node_inputs(
        inputs=solver_node.inputs or {}
    )

    job = Job.create_from_solver(
        solver_id=solver_key, solver_version=version, inputs=job_inputs
    )
    # job.created_at = project.creation_date # FIXME: parse dates
    job = copy_n_update_urls(job, url_for, solver_key, version)
    return job


def create_jobstatus_from_task(task: ComputationTaskOut) -> JobStatus:

    job_status = JobStatus(
        job_id=task.id,
        state=task.state,
        progress=task.guess_progress(),
        submitted_at=datetime.utcnow(),
    )

    # FIXME: timestamp is wrong but at least it will stop run
    if job_status.state in [
        TaskStates.SUCCESS,
        TaskStates.FAILED,
        TaskStates.ABORTED,
    ]:
        job_status.take_snapshot("stopped")
    elif job_status.state in [
        TaskStates.STARTED,
    ]:
        job_status.take_snapshot("started")

    return job_status
