"""
    FIXME: this veeery quick and dirty draft
"""

import itertools
import logging
from copy import deepcopy
from typing import Any, Dict, Generator, Iterator, List, Tuple
from uuid import UUID

from aiohttp import web
from models_library.frontend_services_catalog import is_iterator_service
from models_library.projects import ProjectID
from models_library.projects_nodes import Node, NodeID, OutputID, OutputTypes
from models_library.services import ServiceDockerData

from .meta_funcs import SERVICE_CATALOG, SERVICE_TO_CALLABLES
from .projects.projects_api import get_project_for_user
from .version_control_db import VersionControlRepository
from .version_control_models import CommitID

log = logging.getLogger(__file__)

NodesDict = Dict[NodeID, Node]
NodeOutputsDict = Dict[OutputID, OutputTypes]
Parameters = List[NodeOutputsDict]


def build_project_iterations(project_nodes: NodesDict):

    # select iterable nodes
    iterable_nodes_defs: List[ServiceDockerData] = []  # schemas of iterable nodes
    iterable_nodes: List[Node] = []  # iterable nodes
    iterable_nodes_ids: List[UUID] = []

    for node_id, node in project_nodes.items():
        if is_iterator_service(node.key):
            node_def = SERVICE_CATALOG[(node.key, node.version)]
            # save
            iterable_nodes_defs.append(node_def)
            iterable_nodes.append(node)
            iterable_nodes_ids.append(node_id)

    # for each iterable node create generator
    # NOTE: override branches or keep all?
    nodes_generators = []

    for node, node_def in zip(iterable_nodes, iterable_nodes_defs):
        assert node.inputs
        assert node_def.inputs

        node_call = SERVICE_TO_CALLABLES[(node.key, node.version)]
        g: Generator[NodeOutputsDict, None, None] = node_call(
            **{name: node.inputs[name] for name in node_def.inputs}
        )
        assert isinstance(g, Iterator)
        nodes_generators.append(g)

    project_nodes_iterations: List[NodesDict] = []
    parameters_iterations: List[Tuple[NodeOutputsDict]] = []

    for parameters in itertools.product(*nodes_generators):
        # Q: what if iter are infinite?
        # Q: preview & crop iterations?

        node_results: NodeOutputsDict
        ith_project_nodes: NodesDict = deepcopy(project_nodes)

        for node_results, node_def, node_id in zip(
            parameters, iterable_nodes_defs, iterable_nodes_ids
        ):
            assert node_def.outputs
            assert 1 <= len(node_results) <= len(node_def.outputs)

            # override outputs of corresponding iter
            ith_node = ith_project_nodes[node_id]
            ith_node.outputs = ith_node.outputs or {}
            for output_key, output_value in node_results.items():
                ith_node.outputs[output_key] = output_value

        project_nodes_iterations.append(ith_project_nodes)

    return list(zip(parameters_iterations, project_nodes_iterations))


def extract_parameters(project_nodes: NodesDict) -> Parameters:
    # TODO: iter nodes, if iter, read&save outputs
    # - order?  = order( project_nodes.keys() )
    raise NotImplementedError


async def get_or_create_runnable_projects(
    request: web.Request,
    project_uuid: UUID,
) -> Tuple[List[ProjectID], List[CommitID]]:
    """
    Returns ids and refid of projects that can run
    If project_uuid is a std-project, then it returns itself
    If project_uuid is a meta-project, then it returns iterations
    """

    # FIXME: what happens if not

    vc_repo = VersionControlRepository(request)

    assert vc_repo.user_id  # nosec

    runnable_project_vc_commits: List[CommitID] = []
    runnable_project_ids: List[ProjectID] = [
        project_uuid,
    ]

    project: Dict[str, Any] = await get_project_for_user(
        request.app,
        str(project_uuid),
        user_id=vc_repo.user_id,
        include_templates=False,
        include_state=False,
    )
    project_nodes: Dict[NodeID, Node] = project["workbench"]

    # auto-commit
    repo_id = await vc_repo.get_repo_id(project_uuid)
    if repo_id is None:
        repo_id = await vc_repo.init_repo(project_uuid)

    main_commit_id = await vc_repo.commit(repo_id, message=f"auto:main/{project_uuid}")
    runnable_project_vc_commits.append(main_commit_id)

    # standard project
    is_meta_project = any(
        is_iterator_service(node.key) for node in project_nodes.values()
    )
    if not is_meta_project:
        return runnable_project_ids, runnable_project_vc_commits

    # meta project: resolve project iterations
    runnable_project_ids = []
    runnable_project_vc_commits = []

    iterations = build_project_iterations(project_nodes)
    log.debug(
        "Project %s with %s parameters, produced %s variants",
        project_uuid,
        len(iterations[0]) if iterations else 0,
        len(iterations),
    )

    # Each iteration generates a set of 'parameters'
    #  - parameters are set in the corresponding outputs of the meta-nodes
    #
    for parameters, project_nodes_iteration in iterations:
        log.debug(
            "Creating snapshot of project %s with parameters=%s",
            project_uuid,
            parameters,
        )

        project["workbench"] = project_nodes_iteration

        # hot-commit on branch
        raise NotImplementedError("WIP: force-branch")
        commit_id = await vc_repo.commit(repo_id, message=f"auto/iter/{project_uuid}")
        runnable_project_vc_commits.append(commit_id)

    return runnable_project_ids, runnable_project_vc_commits


async def get_runnable_projects_ids(
    request: web.Request, project_uuid: UUID
) -> List[ProjectID]:
    raise NotImplementedError
