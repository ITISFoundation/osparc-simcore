""" API of computation subsystem within this application

"""
# pylint: disable=too-many-arguments
import datetime
import logging
from pprint import pformat
from typing import Dict, Optional

import psycopg2.errors
import sqlalchemy as sa
from aiohttp import web, web_exceptions
from aiopg.sa import Engine
from aiopg.sa.connection import SAConnection
from celery import Celery
from models_library.projects import RunningState
from servicelib.application_keys import APP_CONFIG_KEY, APP_DB_ENGINE_KEY
from simcore_postgres_database.models.comp_pipeline import StateType
from simcore_postgres_database.webserver_models import (
    NodeClass,
    comp_pipeline,
    comp_tasks,
)
from simcore_sdk.config.rabbit import Config as RabbitConfig

# TODO: move this to computation_models
from simcore_service_webserver.computation_models import to_node_class
from sqlalchemy import and_

from .computation_config import CONFIG_SECTION_NAME as CONFIG_RABBIT_SECTION
from .director import director_api

log = logging.getLogger(__file__)


async def _get_node_details(
    node_key: str, node_version: str, app: web.Application
) -> Dict:
    if "file-picker" in node_key:
        # create a fake file-picker schema here!!
        fake_node_details = {
            "inputs": {},
            "outputs": {
                "outFile": {
                    "label": "the output",
                    "displayOrder": 0,
                    "description": "a file",
                    "type": "data:*/*",
                }
            },
            "type": "dynamic",
        }
        return fake_node_details
    if "frontend/nodes-group" in node_key:
        return None
    if "StimulationSelectivity" in node_key:
        # create a fake file-picker schema here!!
        fake_node_details = {
            "inputs": {},
            "outputs": {
                "stimulationFactor": {
                    "label": "the output",
                    "displayOrder": 0,
                    "description": "a file",
                    "type": "data:*/*",
                    "defaultValue": 0.6,
                }
            },
            "type": "dynamic",
        }
        return fake_node_details
    node_details = await director_api.get_service_by_key_version(
        app, node_key, node_version
    )
    if not node_details:
        log.error(
            "Error (while getting node details) could not find service %s:%s",
            node_key,
            node_version,
        )
        raise web_exceptions.HTTPNotFound(
            reason=f"details of service {node_key}:{node_version} could not be found"
        )
    return node_details


async def _get_node_extras(
    node_key: str, node_version: str, app: web.Application
) -> Dict:
    """Returns the service_extras if possible otherwise None"""
    if to_node_class(node_key) == NodeClass.FRONTEND:
        return None

    node_extras = await director_api.get_services_extras(app, node_key, node_version)
    if not node_extras:
        log.error(
            "Error (while getting node extras) could not find service %s:%s",
            node_key,
            node_version,
        )
        raise web_exceptions.HTTPNotFound(
            reason=f"extras of service {node_key}:{node_version} could not be found"
        )
    return node_extras


async def _build_adjacency_list(
    node_uuid: str,
    node_schema: Dict,
    node_inputs: Dict,
    pipeline_data: Dict,
    dag_adjacency_list: Dict,
    app: web.Application,
) -> Dict:
    if node_inputs is None or node_schema is None:
        return dag_adjacency_list

    for _, input_data in node_inputs.items():
        if input_data is None:
            continue
        is_node_computational = node_schema["type"] == "computational"
        # add it to the list
        if is_node_computational and node_uuid not in dag_adjacency_list:
            dag_adjacency_list[node_uuid] = []

        # check for links
        if isinstance(input_data, dict) and all(
            k in input_data for k in ("nodeUuid", "output")
        ):
            log.debug("decoding link %s", input_data)
            input_node_uuid = input_data["nodeUuid"]
            input_node_details = await _get_node_details(
                pipeline_data[input_node_uuid]["key"],
                pipeline_data[input_node_uuid]["version"],
                app,
            )
            log.debug("input node details %s", input_node_details)
            if input_node_details is None:
                continue
            is_predecessor_computational = input_node_details["type"] == "computational"
            if is_predecessor_computational:
                if input_node_uuid not in dag_adjacency_list:
                    dag_adjacency_list[input_node_uuid] = []
                if (
                    node_uuid not in dag_adjacency_list[input_node_uuid]
                    and is_node_computational
                ):
                    dag_adjacency_list[input_node_uuid].append(node_uuid)
    return dag_adjacency_list


async def _parse_project_data(pipeline_data: Dict, app: web.Application):
    dag_adjacency_list = dict()
    tasks = dict()

    # TODO: we should validate all these things before processing...
    for node_uuid, value in pipeline_data.items():
        if not all(k in value for k in ("key", "version")):
            log.debug("skipping workbench entry containing %s:%s", node_uuid, value)
            continue
        node_key = value["key"]
        node_version = value["version"]

        # get the task data
        node_inputs = None
        if "inputs" in value:
            node_inputs = value["inputs"]
        node_outputs = None
        if "outputs" in value:
            node_outputs = value["outputs"]
        log.debug(
            "node %s:%s has inputs: \n%s\n outputs: \n%s",
            node_key,
            node_version,
            node_inputs,
            node_outputs,
        )

        node_details = await _get_node_details(node_key, node_version, app)
        node_extras = await _get_node_extras(node_key, node_version, app)

        log.debug(
            "node %s:%s has schema:\n %s", node_key, node_version, pformat(node_details)
        )
        if node_details is None:
            continue
        dag_adjacency_list = await _build_adjacency_list(
            node_uuid, node_details, node_inputs, pipeline_data, dag_adjacency_list, app
        )
        log.debug(
            "node %s:%s list updated:\n %s", node_key, node_version, dag_adjacency_list
        )

        # create the task
        node_schema = None
        if not node_details is None:
            node_schema = {
                "inputs": node_details["inputs"],
                "outputs": node_details["outputs"],
            }

        # _get_node_extras returns None ins ome situation, the below checks are required
        requires_gpu = (
            "GPU" in node_extras.get("node_requirements", [])
            if node_extras is not None
            else False
        )
        requires_mpi = (
            "MPI" in node_extras.get("node_requirements", [])
            if node_extras is not None
            else False
        )

        task = {
            "schema": node_schema,
            "inputs": node_inputs,
            "outputs": node_outputs,
            "image": {
                "name": node_key,
                "tag": node_version,
                "requires_gpu": requires_gpu,
                "requires_mpi": requires_mpi,
            },
            "node_class": to_node_class(node_key),
        }

        log.debug("storing task for node %s: %s", node_uuid, task)
        tasks[node_uuid] = task
        log.debug("task stored")
    return dag_adjacency_list, tasks


async def _set_adjacency_in_pipeline_db(
    db_engine: Engine, project_id: str, dag_adjacency_list: Dict
):
    # pylint: disable=no-value-for-parameter
    async with db_engine.acquire() as conn:
        # READ
        # get pipeline
        query = sa.select([comp_pipeline]).where(
            comp_pipeline.c.project_id == project_id
        )
        result = await conn.execute(query)
        pipeline = await result.first()

        # WRITE
        if pipeline is None:
            # create pipeline
            log.debug("No pipeline for project %s, creating one", project_id)
            query = comp_pipeline.insert().values(
                project_id=project_id,
                dag_adjacency_list=dag_adjacency_list,
                state=StateType.NOT_STARTED,
            )
        else:
            # update pipeline
            log.debug("Found pipeline for project %s, updating it", project_id)
            query = (
                comp_pipeline.update()
                .where(comp_pipeline.c.project_id == project_id)
                .values(
                    dag_adjacency_list=dag_adjacency_list, state=StateType.NOT_STARTED
                )
            )

        await conn.execute(query)


async def _set_tasks_in_tasks_db(
    db_engine: Engine, project_id: str, tasks: Dict[str, Dict], replace_pipeline=True
):
    """The replace_pipeline is missleading, it should be interpreted
    as the "RUN" button was pressed on the UI."""
    # pylint: disable=no-value-for-parameter

    async def _task_already_exists(
        conn: SAConnection, project_id: str, node_id: str
    ) -> bool:
        task_count: int = await conn.scalar(
            sa.select([sa.func.count()]).where(
                and_(
                    comp_tasks.c.project_id == project_id,
                    comp_tasks.c.node_id == node_id,
                )
            )
        )
        assert task_count in (  # nosec
            0,
            1,
        ), f"Uniqueness violated: task_count={task_count}"  # nosec
        return task_count != 0

    async def _update_task(
        conn: SAConnection, task: Dict, project_id: str, node_id: str
    ) -> None:
        # update task's inputs/outputs
        io_update = {}
        task_inputs: str = await conn.scalar(
            sa.select([comp_tasks.c.inputs]).where(
                and_(
                    comp_tasks.c.project_id == project_id,
                    comp_tasks.c.node_id == node_id,
                )
            )
        )
        # updates inputs
        if task_inputs != task["inputs"]:
            io_update["inputs"] = task["inputs"]

        # update outputs
        #  NOTE: update ONLY outputs of front-end nodes. The rest are
        #  updated by backend services (e.g. workers, interactive services)
        if task["outputs"] and task["node_class"] == NodeClass.FRONTEND:
            io_update["outputs"] = task["outputs"]

        if io_update:
            query = (
                comp_tasks.update()
                .where(
                    and_(
                        comp_tasks.c.project_id == project_id,
                        comp_tasks.c.node_id == node_id,
                    )
                )
                .values(**io_update)
            )

            await conn.execute(query)

    # MAIN -----------

    async with db_engine.acquire() as conn:

        if replace_pipeline:
            # get project tasks already stored
            query = sa.select([comp_tasks]).where(comp_tasks.c.project_id == project_id)
            result = await conn.execute(query)
            tasks_rows = await result.fetchall()

            # no longer prune database from invalid tasks
            # mark comp tasks with job_id == NULL and set status to 0
            # effectively marking a rest of the pipeline without loosing
            # inputs from comp services
            for task_row in tasks_rows:
                # for some reason the outputs are not present in the
                # tasks outputs. copy them over (will be used below)
                tasks[task_row.node_id]["outputs"] = task_row.outputs
                if not task_row.node_id in tasks:
                    query = (
                        comp_tasks.update()
                        .where(
                            and_(
                                comp_tasks.c.project_id == project_id,
                                comp_tasks.c.node_id == task_row.node_id,
                            )
                        )
                        .values(job_id=None, state=StateType.NOT_STARTED)
                    )
                    await conn.execute(query)

        internal_id = 1
        for node_id, task in tasks.items():

            is_new_task: bool = not await _task_already_exists(
                conn, project_id, node_id
            )
            try:
                if is_new_task:
                    # create task
                    query = comp_tasks.insert().values(
                        project_id=project_id,
                        node_id=node_id,
                        node_class=task["node_class"],
                        internal_id=internal_id,
                        image=task["image"],
                        schema=task["schema"],
                        inputs=task["inputs"],
                        outputs=task["outputs"] if task["outputs"] else {},
                        submit=datetime.datetime.utcnow(),
                    )

                    await conn.execute(query)
                    internal_id = internal_id + 1

            except psycopg2.errors.UniqueViolation:  # pylint: disable=no-member
                # avoids race condition
                is_new_task = False

            if not is_new_task:
                if replace_pipeline:
                    # replace task
                    query = (
                        comp_tasks.update()
                        .where(
                            and_(
                                comp_tasks.c.project_id == project_id,
                                comp_tasks.c.node_id == node_id,
                            )
                        )
                        .values(
                            job_id=None,
                            state=StateType.NOT_STARTED,
                            node_class=task["node_class"],
                            image=task["image"],
                            schema=task["schema"],
                            inputs=task["inputs"],
                            outputs=task["outputs"] if task["outputs"] else {},
                            submit=datetime.datetime.utcnow(),
                        )
                    )
                    await conn.execute(query)
                else:
                    await _update_task(conn, task, project_id, node_id)


#
# API ------------------------------------------
#


async def update_pipeline_db(
    app: web.Application,
    project_id: str,
    project_data: Dict,
    replace_pipeline: bool = True,
) -> None:
    """Updates entries in comp_pipeline and comp_task pg tables for a given project

    :param replace_pipeline: Fully replaces instead of partial updates of existing entries, defaults to True
    """
    db_engine = app[APP_DB_ENGINE_KEY]

    log.debug("Updating pipeline for project %s", project_id)
    dag_adjacency_list, tasks = await _parse_project_data(project_data, app)

    log.debug(
        "Saving dag-list to comp_pipeline table:\n %s", pformat(dag_adjacency_list)
    )
    await _set_adjacency_in_pipeline_db(db_engine, project_id, dag_adjacency_list)

    log.debug("Saving dag-list to comp_tasks table:\n %s", pformat(tasks))
    await _set_tasks_in_tasks_db(db_engine, project_id, tasks, replace_pipeline)

    log.info("Pipeline has been updated for project %s", project_id)


def get_celery(_app: web.Application) -> Celery:
    config = _app[APP_CONFIG_KEY][CONFIG_RABBIT_SECTION]
    rabbit = RabbitConfig(**config)
    celery_app = Celery(
        rabbit.name,
        broker=rabbit.broker_url,
        backend=rabbit.backend,
    )
    return celery_app


async def _set_tasks_in_tasks_db_as_published(db_engine: Engine, project_id: str):
    query = (
        # pylint: disable=no-value-for-parameter
        comp_tasks.update()
        .where(and_(comp_tasks.c.project_id == project_id))
        .values(state=StateType.PUBLISHED)
    )
    async with db_engine.acquire() as conn:
        await conn.execute(query)


async def start_pipeline_computation(
    app: web.Application, user_id: int, project_id: str
) -> Optional[str]:

    db_engine = app[APP_DB_ENGINE_KEY]
    await _set_tasks_in_tasks_db_as_published(db_engine, project_id)

    # publish the tasks to celery
    task = get_celery(app).send_task(
        "comp.task", expires=60, kwargs={"user_id": user_id, "project_id": project_id}
    )
    if not task:
        log.error(
            "Task for user_id %s, project %s could not be started", user_id, project_id
        )
        return

    log.debug(
        "Task (task=%s, user_id=%s, project_id=%s) submitted for execution.",
        task.task_id,
        user_id,
        project_id,
    )
    return task.task_id


def _from_celery_state(celery_state) -> RunningState:
    CELERY_TO_RUNNING_STATE = {
        "PENDING": RunningState.unknown,  # TODO: Celery pending state means unknown
        "STARTED": RunningState.started,
        "RETRY": RunningState.retrying,
        "FAILURE": RunningState.failure,
        "SUCCESS": RunningState.success,
    }
    return RunningState(CELERY_TO_RUNNING_STATE[celery_state])


def convert_state_from_db(db_state: StateType) -> RunningState:
    DB_TO_RUNNING_STATE = {
        StateType.FAILED: RunningState.failure,
        StateType.PENDING: RunningState.pending,
        StateType.SUCCESS: RunningState.success,
        StateType.PUBLISHED: RunningState.published,
        StateType.NOT_STARTED: RunningState.not_started,
        StateType.RUNNING: RunningState.started,
    }
    return RunningState(DB_TO_RUNNING_STATE[StateType(db_state)])


async def get_task_states(
    app: web.Application, project_id: str
) -> Dict[str, RunningState]:
    db_engine = app[APP_DB_ENGINE_KEY]
    task_states: Dict[str, RunningState] = {}
    async with db_engine.acquire() as conn:
        async for row in conn.execute(
            sa.select([comp_tasks]).where(comp_tasks.c.project_id == project_id)
        ):
            if row.node_class != NodeClass.COMPUTATIONAL:
                continue
            task_states[row.node_id] = convert_state_from_db(row.state)

            # the task might be running, better ask celery (NOTE this remains only 24h and disappears and state will be pending)
            # task_result = AsyncResult(row.job_id)

            # running_state = _from_celery_state(task_result.state)
            # task_states[row.node_id] = running_state
    return task_states


async def get_pipeline_state(app: web.Application, project_id: str) -> RunningState:
    task_states: Dict[str, RunningState] = await get_task_states(app, project_id)
    # compute pipeline state from task states
    if task_states:
        # put in a set of unique values
        set_states = set(task_states.values())
        if len(set_states) == 1:
            # this is typically for success, pending, published
            return next(iter(set_states))

        for state in [
            RunningState.published,  # still in publishing phase
            RunningState.started,  # task is started or retrying
            RunningState.failure,  # task is failed -> pipeline as well
        ]:
            if any(x == state for x in set_states):
                return state

    return RunningState.not_started


async def delete_pipeline_db(app: web.Application, project_id: str) -> None:
    db_engine = app[APP_DB_ENGINE_KEY]

    async with db_engine.acquire() as conn:
        # pylint: disable=no-value-for-parameter
        query = comp_tasks.delete().where(comp_tasks.c.project_id == project_id)
        await conn.execute(query)
        query = comp_pipeline.delete().where(comp_pipeline.c.project_id == project_id)
        await conn.execute(query)


async def get_task_output(
    app: web.Application, project_id: str, node_id: str
) -> Optional[Dict]:
    db_engine = app[APP_DB_ENGINE_KEY]
    async with db_engine.acquire() as conn:
        query = sa.select([comp_tasks]).where(
            and_(comp_tasks.c.project_id == project_id, comp_tasks.c.node_id == node_id)
        )
        result = await conn.execute(query)
        comp_task = await result.fetchone()
        if comp_task:
            return comp_task.outputs
