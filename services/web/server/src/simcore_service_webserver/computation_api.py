""" API of computation subsystem within this application

"""
import datetime
import logging
from pprint import pformat
from typing import Dict, Optional

import sqlalchemy as sa
from aiohttp import web, web_exceptions
from aiopg.sa import Engine
from sqlalchemy import and_

from servicelib.application_keys import APP_DB_ENGINE_KEY
from simcore_postgres_database.models.comp_pipeline import UNKNOWN
from simcore_postgres_database.webserver_models import comp_pipeline, comp_tasks

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
        log.error("Error could not find service %s:%s", node_key, node_version)
        raise web_exceptions.HTTPNotFound(
            reason=f"details of service {node_key}:{node_version} could not be found"
        )
    return node_details


async def _build_adjacency_list(
    node_uuid: str,
    node_schema: Dict,
    node_inputs: Dict,
    pipeline_data: Dict,
    dag_adjacency_list: Dict,
    app: web.Application,
) -> Dict:  # pylint: disable=too-many-arguments
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
        task = {
            "schema": node_schema,
            "inputs": node_inputs,
            "outputs": node_outputs,
            "image": {"name": node_key, "tag": node_version},
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
                state=UNKNOWN,
            )
        else:
            # update pipeline
            log.debug("Found pipeline for project %s, updating it", project_id)
            query = (
                comp_pipeline.update()
                .where(comp_pipeline.c.project_id == project_id)
                .values(dag_adjacency_list=dag_adjacency_list, state=UNKNOWN)
            )

        await conn.execute(query)


async def _set_tasks_in_tasks_db(
    db_engine: Engine, project_id: str, tasks: Dict[str, Dict], replace_pipeline=True
):
    # pylint: disable=no-value-for-parameter
    async with db_engine.acquire() as conn:

        if replace_pipeline:
            # get project tasks already stored
            query = sa.select([comp_tasks]).where(comp_tasks.c.project_id == project_id)
            result = await conn.execute(query)
            tasks_rows = await result.fetchall()

            # prune database from invalid tasks
            for task_row in tasks_rows:
                if not task_row.node_id in tasks:
                    query = comp_tasks.delete().where(
                        and_(
                            comp_tasks.c.project_id == project_id,
                            comp_tasks.c.node_id == task_row.node_id,
                        )
                    )
                    await conn.execute(query)

        internal_id = 1
        for node_id, task in tasks.items():
            # READ
            # get task
            query = sa.select([comp_tasks]).where(
                and_(
                    comp_tasks.c.project_id == project_id,
                    comp_tasks.c.node_id == node_id,
                )
            )
            result = await conn.execute(query)
            task_row = await result.fetchone()

            # WRITE
            if task_row is None:
                # create task
                query = comp_tasks.insert().values(
                    project_id=project_id,
                    node_id=node_id,
                    internal_id=internal_id,
                    image=task["image"],
                    schema=task["schema"],
                    inputs=task["inputs"],
                    outputs=task["outputs"] if task["outputs"] else {},
                    submit=datetime.datetime.utcnow(),
                )

                await conn.execute(query)
                internal_id = internal_id + 1
            else:
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
                            state=UNKNOWN,
                            image=task["image"],
                            schema=task["schema"],
                            inputs=task["inputs"],
                            outputs=task["outputs"] if task["outputs"] else {},
                            submit=datetime.datetime.utcnow(),
                        )
                    )
                    await conn.execute(query)
                else:
                    # update task
                    cols_to_update = {}
                    if task_row["inputs"] != task["inputs"]:
                        cols_to_update["inputs"] = task["inputs"]
                    if task["outputs"]:
                        cols_to_update["outputs"] = task["outputs"]

                    if cols_to_update:
                        query = (
                            comp_tasks.update()
                            .where(
                                and_(
                                    comp_tasks.c.project_id == project_id,
                                    comp_tasks.c.node_id == node_id,
                                )
                            )
                            .values(**cols_to_update)
                        )

                        await conn.execute(query)


#
# API ------------------------------------------
#


async def update_pipeline_db(
    app: web.Application,
    project_id: str,
    project_data: Dict,
    replace_pipeline: bool = True,
) -> None:
    """ Updates entries in comp_pipeline and comp_task pg tables for a given project

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
