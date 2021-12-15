"""
    TODO: refactor logic into different modules
"""

import itertools
import json
import logging
import re
from copy import deepcopy
from typing import Any, Dict, Generator, Iterator, List, Literal, Optional, Tuple, Union

from aiohttp import web
from models_library.basic_types import MD5Str, SHA1Str
from models_library.frontend_services_catalog import is_iterator_service
from models_library.projects import ProjectID
from models_library.projects_nodes import Node, NodeID, OutputID, OutputTypes
from models_library.services import ServiceDockerData
from pydantic import BaseModel, ValidationError
from pydantic.fields import Field

from .meta_funcs import (
    SERVICE_CATALOG,
    SERVICE_TO_CALLABLES,
    create_param_node_from_iterator_with_outputs,
)
from .meta_version_control import CommitID, ProjectDict, VersionControlForMetaModeling
from .utils import compute_sha1

log = logging.getLogger(__file__)


NodesDict = Dict[NodeID, Node]
NodeOutputsDict = Dict[OutputID, OutputTypes]
Parameters = Tuple[NodeOutputsDict]
_ParametersNodesPair = Tuple[Parameters, NodesDict]


def _compute_params_checksum(parameters: Parameters) -> MD5Str:
    # TODO: test non-std OutputTypes
    return compute_sha1(parameters)


def _build_project_iterations(project_nodes: NodesDict) -> List[_ParametersNodesPair]:
    """Builds changing instances (i.e. iterations) of the meta-project

    This interface only knows about project/node models and parameters
    """

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
            _iter_node = deepcopy(project_nodes[node_id])
            _iter_node.outputs = _iter_node.outputs or {}
            _iter_node.outputs.update(node_results)

            # TODO: tmp we replace iter_node by a param_node
            _param_node = create_param_node_from_iterator_with_outputs(_iter_node)
            updated_nodes[node_id] = _param_node

        # FIXME: here we yield.
        parameters_per_iter.append(parameters)
        updated_nodes_per_iter.append(updated_nodes)

    return list(zip(parameters_per_iter, updated_nodes_per_iter))


def extract_parameters(
    vc_repo: VersionControlForMetaModeling,
    project_uuid: ProjectID,
    commit_id: CommitID,
) -> Parameters:
    # TODO: get snapshot

    # TODO: iter nodes, if iter, read&save outputs
    # - order?  = order( project_nodes.keys() )

    raise NotImplementedError()


# DOMAIN MODEL for project iteration -----


class ProjectIteration(BaseModel):
    """
    - Keeps a reference of the version: vc repo/commit and wcopy
    - Keeps a reference of the interation: order, parameters (for the moment, only hash), ...

    - de/serializes from/to a vc tag
    """

    # version-control info
    repo_id: Optional[int] = None
    repo_commit_id: CommitID = Field(...)

    # iteration info
    iter_index: int = Field(...)
    total_count: Union[int, Literal["unbound"]] = "unbound"
    parameters_checksum: SHA1Str = Field(...)

    @classmethod
    def from_tag_name(
        cls, tag_name: str, *, return_none_if_fails: bool = False
    ) -> Optional["ProjectIteration"]:
        """Parses iteration info from tag name"""
        try:
            return cls.parse_obj(parse_iteration_tag_name(tag_name))
        except ValidationError as err:
            if return_none_if_fails:
                log.debug("%s", f"{err=}")
                return None
            raise

    def to_tag_name(self) -> str:
        """Composes unique tag name for this iteration"""
        return compose_iteration_tag_name(
            repo_commit_id=self.repo_commit_id,
            iter_index=self.iter_index,
            total_count=self.total_count,
            parameters_checksum=self.parameters_checksum,
        )


def compose_iteration_tag_name(
    repo_commit_id: CommitID,
    iter_index: int,
    total_count: Union[int, str],
    parameters_checksum: SHA1Str,
) -> str:
    """Composes unique tag name for iter_index-th iteration of repo_commit_id out of total_count"""
    # NOTE: prefers to a json dump because it allows regex search?
    # should be searchable e.g. get repo/*/*/*
    # can do the same with json since it is a str!?
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

    vc_repo = VersionControlForMetaModeling(request)
    assert vc_repo.user_id  # nosec

    # TODO:  handle UserUndefined and translate into web.HTTPForbidden
    project: ProjectDict = await vc_repo.get_project(str(project_uuid))

    project_nodes: Dict[NodeID, Node] = {
        nid: Node.parse_obj(n) for nid, n in project["workbench"].items()
    }

    # init returns
    runnable_project_vc_commits: List[CommitID] = []
    runnable_project_ids: List[ProjectID] = [
        project_uuid,
    ]

    # auto-commit
    #   because it will run in parallel -> needs an independent working copy
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
    original_name = project["name"]

    for iter_index, (parameters, updated_nodes) in enumerate(iterations):
        log.debug(
            "Creating snapshot of project %s with parameters=%s",
            project_uuid,
            parameters,
        )

        project["name"] = f"{original_name}/{iter_index}"
        project["workbench"].update(
            {
                # converts model in dict patching first thumbnail
                nid: n.copy(update={"thumbnail": n.thumbnail or ""}).dict(
                    by_alias=True, exclude_unset=True
                )
                for nid, n in updated_nodes.items()
            }
        )

        project_iteration = ProjectIteration(
            repo_id=repo_id,
            repo_commit_id=main_commit_id,
            iter_index=iter_index,
            total_count=total_count,
            parameters_checksum=_compute_params_checksum(parameters),
        )

        # tag to identify this iteration
        branch_name = tag_name = project_iteration.to_tag_name()

        commit_id = await vc_repo.force_branch_and_wcopy(
            repo_id,
            start_commit_id=main_commit_id,
            project=project,
            branch_name=branch_name,
            tag_name=tag_name,
            tag_message=json.dumps(parameters),
        )

        wcopy_project_id = await vc_repo.get_wcopy_project_id(repo_id, commit_id)

        runnable_project_ids.append(ProjectID(wcopy_project_id))
        runnable_project_vc_commits.append(commit_id)

    return runnable_project_ids, runnable_project_vc_commits


async def get_runnable_projects_ids(
    request: web.Request,
    project_uuid: ProjectID,
) -> List[ProjectID]:

    vc_repo = VersionControlForMetaModeling(request)
    assert vc_repo.user_id  # nosec

    project: ProjectDict = await vc_repo.get_project(str(project_uuid))
    assert project["uuid"] == str(project_uuid)  # nosec
    project_nodes: Dict[NodeID, Node] = {
        nid: Node.parse_obj(n) for nid, n in project["workbench"].items()
    }

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
