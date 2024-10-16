"""
    Helper functions to convert models used in
    services/api-server/src/simcore_service_api_server/api/routes/solvers_jobs.py
"""

import urllib.parse
import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from functools import lru_cache

import arrow
from models_library.api_schemas_webserver.projects import ProjectCreateNew, ProjectGet
from models_library.basic_types import KeyIDStr
from models_library.projects_nodes import InputID
from pydantic import TypeAdapter

from ..models.basic_types import VersionStr
from ..models.domain.projects import InputTypes, Node, SimCoreFileLink, StudyUI
from ..models.schemas.files import File
from ..models.schemas.jobs import (
    ArgumentTypes,
    Job,
    JobInputs,
    JobStatus,
    PercentageInt,
)
from ..models.schemas.solvers import Solver, SolverKeyId
from .director_v2 import ComputationTaskGet

# UTILS ------
_BASE_UUID = uuid.UUID("231e13db-6bc6-4f64-ba56-2ee2c73b9f09")


@lru_cache
def compose_uuid_from(*values) -> str:
    composition = "/".join(map(str, values))
    new_uuid = uuid.uuid5(_BASE_UUID, composition)
    return str(new_uuid)


def format_datetime(snapshot: datetime) -> str:
    return "{}Z".format(snapshot.isoformat(timespec="milliseconds"))


def now_str() -> str:
    # NOTE: backend MUST use UTC
    return format_datetime(datetime.now(timezone.utc))


# CONVERTERS --------------
#
# - creates a model in one API composing models in others
#


def create_node_inputs_from_job_inputs(
    inputs: JobInputs,
) -> dict[InputID, InputTypes]:
    # map Job inputs with solver inputs
    # TODO: ArgumentType -> InputTypes dispatcher

    node_inputs: dict[InputID, InputTypes] = {}
    for name, value in inputs.values.items():
        assert TypeAdapter(ArgumentTypes).validate_python(value) == value  # type: ignore # nosec
        assert TypeAdapter(KeyIDStr).validate_python(name) is not None  # nosec

        if isinstance(value, File):
            # FIXME: ensure this aligns with storage policy
            node_inputs[KeyIDStr(name)] = SimCoreFileLink(
                store=0,
                path=f"api/{value.id}/{value.filename}",
                label=value.filename,
                eTag=value.e_tag,
            )
        else:
            node_inputs[KeyIDStr(name)] = value

    # TODO: validate Inputs??

    return node_inputs


def create_job_inputs_from_node_inputs(inputs: dict[InputID, InputTypes]) -> JobInputs:
    """Reverse  from create_node_inputs_from_job_inputs

    raises ValidationError
    """
    input_values: dict[str, ArgumentTypes] = {}
    for name, value in inputs.items():
        assert TypeAdapter(InputID).validate_python(name) == name  # nosec
        assert TypeAdapter(InputTypes).validate_python(value) == value  # nosec

        if isinstance(value, SimCoreFileLink):
            # FIXME: ensure this aligns with storage policy
            _api, file_id, filename = value.path.split("/")
            assert _api == "api"  # nosec
            input_values[name] = File(
                id=file_id,  # type: ignore[arg-type]
                filename=filename,
                e_tag=value.e_tag,
            )
        else:
            # NOTE: JobInputs pydantic model will parse&validate these values
            input_values[name] = value  # type: ignore [assignment]

    return JobInputs(values=input_values)  # raises ValidationError


def get_node_id(project_id, solver_id) -> str:
    # By clumsy design, the webserver needs a global uuid,
    # so we decieded to compose as this
    return compose_uuid_from(project_id, solver_id)


def create_new_project_for_job(
    solver: Solver, job: Job, inputs: JobInputs
) -> ProjectCreateNew:
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

    # map Job inputs with solveri nputs
    # TODO: ArgumentType -> InputTypes dispatcher and reversed
    solver_inputs: dict[InputID, InputTypes] = create_node_inputs_from_job_inputs(
        inputs
    )

    solver_service = Node(
        key=solver.id,
        version=solver.version,
        label=solver.title,
        inputs=solver_inputs,
        inputsUnits={},
    )

    # Ensembles project model so it can be used as input for create_project
    job_info = job.model_dump_json(
        include={"id", "name", "inputs_checksum", "created_at"}, indent=2
    )

    return ProjectCreateNew(
        uuid=project_id,
        name=job.name,  # NOTE: this IS an identifier as well. MUST NOT be changed in the case of project APIs!
        description=f"Study associated to solver job:\n{job_info}",
        thumbnail="https://via.placeholder.com/170x120.png",  # type: ignore[arg-type]
        workbench={solver_id: solver_service},
        ui=StudyUI(
            workbench={
                f"{solver_id}": {  # type: ignore[dict-item]
                    "position": {
                        "x": 633,
                        "y": 229,
                    },
                },
            },
            slideshow={},
            currentNodeId=solver_id,  # type: ignore[arg-type]
            annotations={},
        ),
        accessRights={},  # type: ignore[call-arg]  # This MUST be called with alias
    )


def create_job_from_project(
    solver_key: SolverKeyId,
    solver_version: VersionStr,
    project: ProjectGet,
    url_for: Callable,
) -> Job:
    """
    Given a project, creates a job

    - Complementary from create_project_from_job
    - Assumes project created via solver's job

    raise ValidationError
    """
    assert len(project.workbench) == 1  # nosec
    assert solver_version in project.name  # nosec
    assert urllib.parse.quote_plus(solver_key) in project.name  # nosec

    # get solver node
    node_id = next(iter(project.workbench.keys()))
    solver_node: Node = project.workbench[node_id]
    job_inputs: JobInputs = create_job_inputs_from_node_inputs(
        inputs=solver_node.inputs or {}
    )

    # create solver's job
    solver_name = Solver.compose_resource_name(solver_key, solver_version)

    job_id = project.uuid

    job = Job(
        id=job_id,
        name=project.name,
        inputs_checksum=job_inputs.compute_checksum(),
        created_at=project.creation_date,  # type: ignore[arg-type]
        runner_name=solver_name,
        url=url_for(
            "get_job",
            solver_key=solver_key,
            version=solver_version,
            job_id=job_id,
        ),
        runner_url=url_for(
            "get_solver_release",
            solver_key=solver_key,
            version=solver_version,
        ),
        outputs_url=url_for(
            "get_job_outputs",
            solver_key=solver_key,
            version=solver_version,
            job_id=job_id,
        ),
    )

    assert all(
        getattr(job, f) for f in job.model_fields.keys() if f.endswith("url")
    )  # nosec

    return job


def create_jobstatus_from_task(task: ComputationTaskGet) -> JobStatus:
    return JobStatus(
        job_id=task.id,
        state=task.state,
        progress=PercentageInt((task.pipeline_details.progress or 0) * 100.0),
        submitted_at=task.submitted or arrow.utcnow().datetime,
        started_at=task.started,
        stopped_at=task.stopped,
    )
