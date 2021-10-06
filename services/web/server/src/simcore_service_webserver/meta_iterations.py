"""
    FIXME: this veeery quick and dirty draft
"""

import itertools
import json
import logging
import re
from copy import deepcopy
from typing import Any, Dict, Generator, Iterator, List, Tuple

from aiohttp import web
from models_library.basic_types import MD5Str
from models_library.frontend_services_catalog import is_iterator_service
from models_library.projects import ProjectID
from models_library.projects_nodes import Node, NodeID, OutputID, OutputTypes
from models_library.services import ServiceDockerData

from .meta_funcs import SERVICE_CATALOG, SERVICE_TO_CALLABLES
from .projects.projects_api import get_project_for_user
from .utils import compute_sha1
from .version_control_db import VersionControlRepositoryInternalAPI
from .version_control_models import CommitID

log = logging.getLogger(__file__)


NodesDict = Dict[NodeID, Node]
NodeOutputsDict = Dict[OutputID, OutputTypes]
Parameters = Tuple[NodeOutputsDict]
_ParametersNodesPair = Tuple[Parameters, NodesDict]


def _compute_params_checksum(parameters: Parameters) -> MD5Str:
    # TODO: test non-std OutputTypes
    return compute_sha1(parameters)


def _build_project_iterations(project_nodes: NodesDict) -> List[_ParametersNodesPair]:

    # select iterable nodes
    iterable_nodes_defs: List[ServiceDockerData] = []  # schemas of iterable nodes
    iterable_nodes: List[Node] = []  # iterable nodes
    iterable_nodes_ids: List[NodeID] = []

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
        assert node.inputs  # nosec
        assert node_def.inputs  # nosec

        node_call = SERVICE_TO_CALLABLES[(node.key, node.version)]
        g: Generator[NodeOutputsDict, None, None] = node_call(
            **{name: node.inputs[name] for name in node_def.inputs}
        )
        assert isinstance(g, Iterator)  # nosec
        nodes_generators.append(g)

    updated_nodes_per_iter: List[NodesDict] = []
    parameters_per_iter: List[Tuple[NodeOutputsDict]] = []

    for parameters in itertools.product(*nodes_generators):
        # Q: what if iter are infinite?
        # Q: preview & crop iterations?

        node_results: NodeOutputsDict
        updated_nodes: NodesDict = {}

        for node_results, node_def, node_id in zip(
            parameters, iterable_nodes_defs, iterable_nodes_ids
        ):
            assert node_def.outputs  # nosec
            assert 1 <= len(node_results) <= len(node_def.outputs)  # nosec

            # override outputs with the parametrization results
            _node = updated_nodes[node_id] = deepcopy(project_nodes[node_id])
            _node.outputs = _node.outputs or {}
            _node.outputs.update(node_results)

        parameters_per_iter.append(parameters)
        updated_nodes_per_iter.append(updated_nodes)

    return list(zip(parameters_per_iter, updated_nodes_per_iter))


def extract_parameters(
    vc_repo: VersionControlRepositoryInternalAPI,
    project_uuid: ProjectID,
    commit_id: CommitID,
) -> Parameters:
    # TODO: get snapshot

    # TODO: iter nodes, if iter, read&save outputs
    # - order?  = order( project_nodes.keys() )

    raise NotImplementedError()


# TAGGING iterations -----


def compose_iteration_tag_name(
    repo_commit_id, iter_index, total_count, parameters_checksum
) -> str:
    """Composes unique tag name for iter_index-th iteration of repo_commit_id out of total_count"""
    return (
        f"iteration:{repo_commit_id}/{iter_index}/{total_count}/{parameters_checksum}"
    )


def parse_iteration_tag_name(name: str) -> Dict[str, Any]:
    if m := re.match(
        r"^iteration:(?P<repo_commit_id>\d+)/(?P<iter_index>\d+)/(?P<total_count>-*\d+)/(?P<parameters_checksum>.*)$",
        name,
    ):
        return m.groupdict()
    return {}


# GET/CREATE iterations -----------


async def get_or_create_runnable_projects(
    request: web.Request,
    project_uuid: ProjectID,
) -> Tuple[List[ProjectID], List[CommitID]]:
    """
    Returns ids and refid of projects that can run
    If project_uuid is a std-project, then it returns itself
    If project_uuid is a meta-project, then it returns iterations
    """

    # FIXME: what happens if not

    vc_repo = VersionControlRepositoryInternalAPI(request)
    assert vc_repo.user_id  # nosec

    # retrieves project
    project = await get_project_for_user(
        request.app,
        project_uuid=str(project_uuid),
        user_id=vc_repo.user_id,
        include_state=False,
        include_templates=False,
    )
    assert project["uuid"] == str(project_uuid)  # nosec
    # FIXME: same project but different views
    #  assert project == await vc_repo.get_project(project_uuid)

    project_nodes: Dict[NodeID, Node] = {
        nid: Node.parse_obj(n) for nid, n in project["workbench"].items()
    }

    # init returns
    runnable_project_vc_commits: List[CommitID] = []
    runnable_project_ids: List[ProjectID] = [
        project_uuid,
    ]

    # auto-commit
    repo_id = await vc_repo.get_repo_id(project_uuid)
    if repo_id is None:
        repo_id = await vc_repo.init_repo(project_uuid)

    main_commit_id = await vc_repo.commit(
        repo_id,
        tag=f"auto:main/{project_uuid}",
        message="auto-commit at get_or_create_runnable_projects",
    )
    runnable_project_vc_commits.append(main_commit_id)

    # std-project
    is_meta_project = any(
        is_iterator_service(node.key) for node in project_nodes.values()
    )
    if not is_meta_project:
        return runnable_project_ids, runnable_project_vc_commits

    # meta-project: resolve project iterations
    runnable_project_ids = []
    runnable_project_vc_commits = []

    iterations = _build_project_iterations(project_nodes)
    log.debug(
        "Project %s with %s parameters, produced %s variants",
        project_uuid,
        len(iterations[0]) if iterations else 0,
        len(iterations),
    )

    # Each iteration generates a set of 'parameters'
    #  - parameters are set in the corresponding outputs of the meta-nodes
    #
    parameters: Parameters
    updated_nodes: NodesDict
    total_count = len(iterations)

    for iter_index, (parameters, updated_nodes) in enumerate(iterations):
        log.debug(
            "Creating snapshot of project %s with parameters=%s",
            project_uuid,
            parameters,
        )

        project["workbench"].update(updated_nodes)

        # tag to identify this iteration
        branch_name = tag_name = compose_iteration_tag_name(
            main_commit_id,
            iter_index,
            total_count,
            _compute_params_checksum(parameters),
        )

        commit_id = await vc_repo.force_branch_and_wcopy(
            repo_id,
            start_commit_id=main_commit_id,
            project=project,
            branch_name=branch_name,
            tag_name=tag_name,
            tag_message=json.dumps(parameters),
        )

        wcopy_project_id = await vc_repo.get_wcopy_project_id(repo_id, commit_id)
        assert project["uuid"] == wcopy_project_id  # nosec

        runnable_project_ids.append(wcopy_project_id)
        runnable_project_vc_commits.append(commit_id)

    return runnable_project_ids, runnable_project_vc_commits


async def get_runnable_projects_ids(
    request: web.Request,
    project_uuid: ProjectID,
) -> List[ProjectID]:

    vc_repo = VersionControlRepositoryInternalAPI(request)
    assert vc_repo.user_id  # nosec

    project = await get_project_for_user(
        request.app,
        project_uuid=str(project_uuid),
        user_id=vc_repo.user_id,
        include_state=False,
        include_templates=False,
    )
    assert project["uuid"] == str(project_uuid)  # nosec

    project_nodes: Dict[NodeID, Node] = project["workbench"]

    # init returns
    runnable_project_ids: List[ProjectID] = []

    # std-project
    is_meta_project = any(
        is_iterator_service(node.key) for node in project_nodes.values()
    )
    if not is_meta_project:
        runnable_project_ids.append(project_uuid)
        return runnable_project_ids

    # meta-project
    # TODO: find branches of current head that represents iterations
    # tags: - one to identify it as iteration with given parameters
    #       - one to associate runnable project uuid
    raise NotImplementedError()
