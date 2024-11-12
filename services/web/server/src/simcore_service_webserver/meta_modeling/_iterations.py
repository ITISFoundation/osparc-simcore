""" Implements parts of the pre-run stage that iterates a meta-project and versions every iteration

"""

import itertools
import logging
import re
from collections.abc import Iterator
from copy import deepcopy
from typing import Any, Literal, Optional

from aiohttp import web
from common_library.json_serialization import json_dumps
from models_library.basic_types import KeyIDStr, SHA1Str
from models_library.function_services_catalog import is_iterator_service
from models_library.projects import ProjectID
from models_library.projects_nodes import Node, OutputID, OutputTypes
from models_library.projects_nodes_io import NodeID
from models_library.services import ServiceMetaDataPublished
from pydantic import BaseModel, ValidationError
from pydantic.fields import Field
from pydantic.types import PositiveInt

from .._constants import RQ_PRODUCT_KEY
from ..projects.models import ProjectDict
from ..utils import compute_sha1_on_small_dataset, now_str
from ..version_control.errors import UserUndefinedError
from ..version_control.models import CommitID
from . import _function_nodes
from ._version_control import VersionControlForMetaModeling

_logger = logging.getLogger(__name__)


NodesDict = dict[NodeID, Node]
NodeOutputsDict = dict[OutputID, OutputTypes]
Parameters = tuple[NodeOutputsDict]
_ParametersNodesPair = tuple[Parameters, NodesDict]


def _compute_params_checksum(parameters: Parameters) -> SHA1Str:
    # NOTE: parameters are within a project's dataset which can
    # be considered small (based on test_compute_sh1_on_small_dataset)
    return compute_sha1_on_small_dataset(parameters)


def _build_project_iterations(project_nodes: NodesDict) -> list[_ParametersNodesPair]:
    """Builds changing instances (i.e. iterations) of the meta-project

    This interface only knows about project/node models and parameters
    """

    # select iterable nodes
    iterable_nodes_defs: list[
        ServiceMetaDataPublished
    ] = []  # schemas of iterable nodes
    iterable_nodes: list[Node] = []  # iterable nodes
    iterable_nodes_ids: list[NodeID] = []

    for node_id, node in project_nodes.items():
        if is_iterator_service(node.key):
            node_def = _function_nodes.catalog.get_metadata(node.key, node.version)
            # save
            iterable_nodes_defs.append(node_def)
            iterable_nodes.append(node)
            iterable_nodes_ids.append(node_id)

    # for each iterable node create generator
    nodes_generators = []

    for node, node_def in zip(iterable_nodes, iterable_nodes_defs):
        assert node.inputs  # nosec
        assert node_def.inputs  # nosec

        node_call = _function_nodes.catalog.get_implementation(node.key, node.version)
        assert node_call  # nosec
        g = node_call(
            **{f"{name}": node.inputs[KeyIDStr(name)] for name in node_def.inputs}
        )
        assert isinstance(g, Iterator)  # nosec
        nodes_generators.append(g)

    updated_nodes_per_iter: list[NodesDict] = []
    parameters_per_iter: list[tuple[NodeOutputsDict]] = []

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

            # NOTE: Replacing iter_node by a param_node, it avoid re-running matching iterations
            #       Currently it does not work because front-end needs to change
            # SEE https://github.com/ITISFoundation/osparc-simcore/issues/2735
            #
            updated_nodes[node_id] = _iter_node

        parameters_per_iter.append(parameters)
        updated_nodes_per_iter.append(updated_nodes)

    return list(zip(parameters_per_iter, updated_nodes_per_iter))


def extract_parameters(
    vc_repo: VersionControlForMetaModeling,
    project_uuid: ProjectID,
    commit_id: CommitID,
) -> Parameters:
    raise NotImplementedError
    # SEE https://github.com/ITISFoundation/osparc-simcore/issues/2735


# DOMAIN MODEL for project iteration ------------------------------------------------------------

IterationID = PositiveInt


class ProjectIteration(BaseModel):
    """
    - Keeps a reference of the version: vc repo/commit and workcopy
    - Keeps a reference of the interation: order, parameters (for the moment, only hash), ...

    - de/serializes from/to a vc tag
    """

    # version-control info
    repo_id: int | None = None
    repo_commit_id: CommitID = Field(
        ...,
        description="this id makes it unique but does not guarantees order. See iter_index for that",
    )

    # iteration info
    iteration_index: IterationID = Field(
        ...,
        description="Index that allows iterations to be sortable",
    )
    total_count: int | Literal["unbound"] = "unbound"
    parameters_checksum: SHA1Str = Field(...)

    @classmethod
    def from_tag_name(
        cls, tag_name: str, *, return_none_if_fails: bool = False
    ) -> Optional["ProjectIteration"]:
        """Parses iteration info from tag name"""
        try:
            return cls.model_validate(parse_iteration_tag_name(tag_name))
        except ValidationError as err:
            if return_none_if_fails:
                _logger.debug("%s", f"{err=}")
                return None
            raise

    def to_tag_name(self) -> str:
        """Composes unique tag name for this iteration"""
        return compose_iteration_tag_name(
            repo_commit_id=self.repo_commit_id,
            iteration_index=self.iteration_index,
            total_count=self.total_count,
            parameters_checksum=self.parameters_checksum,
        )


# NOTE: compose_/parse_ functions are basically serialization functions for ProjectIteration
#       into/from string tags. An alternative approach would be simply using json.dump/load
#       but we should guarantee backwards compatibilty with old tags
def compose_iteration_tag_name(
    repo_commit_id: CommitID,
    iteration_index: IterationID,
    total_count: int | str,
    parameters_checksum: SHA1Str,
) -> str:
    """Composes unique tag name for iter_index-th iteration of repo_commit_id out of total_count"""
    return f"iteration:{repo_commit_id}/{iteration_index}/{total_count}/{parameters_checksum}"


def parse_iteration_tag_name(name: str) -> dict[str, Any]:
    if m := re.match(
        r"^iteration:(?P<repo_commit_id>\d+)/(?P<iteration_index>\d+)/(?P<total_count>-*\d+)/(?P<parameters_checksum>.*)$",
        name,
    ):
        return m.groupdict()
    return {}


# GET/CREATE iterations ------------------------------------------------------------


async def get_or_create_runnable_projects(
    request: web.Request,
    project_uuid: ProjectID,
) -> tuple[list[ProjectID], list[CommitID]]:
    """
    Returns ids and refid of projects that can run
    If project_uuid is a std-project, then it returns itself
    If project_uuid is a meta-project, then it returns iterations
    """

    vc_repo = VersionControlForMetaModeling.create_from_request(request)
    assert vc_repo.user_id  # nosec
    product_name = request[RQ_PRODUCT_KEY]

    try:
        project: ProjectDict = await vc_repo.get_project(str(project_uuid))
    except UserUndefinedError as err:
        raise web.HTTPForbidden(reason="Unauthenticated request") from err

    project_nodes: dict[NodeID, Node] = {
        nid: Node.model_validate(n) for nid, n in project["workbench"].items()
    }

    # init returns
    runnable_project_vc_commits: list[CommitID] = []
    runnable_project_ids: list[ProjectID] = [
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
        message=f"auto-commit {now_str()}",
    )
    runnable_project_vc_commits.append(main_commit_id)

    # std-project
    is_meta_project = any(
        is_iterator_service(node.key) and not node.outputs
        for node in project_nodes.values()
    )
    if not is_meta_project:
        return runnable_project_ids, runnable_project_vc_commits

    # meta-project: resolve project iterations
    runnable_project_ids = []
    runnable_project_vc_commits = []

    iterations = _build_project_iterations(project_nodes)
    _logger.debug(
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

    for iteration_index, (parameters, updated_nodes) in enumerate(iterations, start=1):
        _logger.debug(
            "Creating snapshot of project %s with parameters=%s [%s]",
            f"{project_uuid=}",
            f"{parameters=}",
            f"{updated_nodes=}",
        )

        project["name"] = f"{original_name}/{iteration_index}"
        project["workbench"].update(
            {
                # converts model in dict patching first thumbnail
                nid: n.model_copy(update={"thumbnail": n.thumbnail or ""}).model_dump(
                    by_alias=True, exclude_unset=True
                )
                for nid, n in updated_nodes.items()
            }
        )

        project_iteration = ProjectIteration(
            repo_id=repo_id,
            repo_commit_id=main_commit_id,
            iteration_index=iteration_index,
            total_count=total_count,
            parameters_checksum=_compute_params_checksum(parameters),
        )

        # tag to identify this iteration
        branch_name = tag_name = project_iteration.to_tag_name()

        commit_id = await vc_repo.create_workcopy_and_branch_from_commit(
            repo_id,
            start_commit_id=main_commit_id,
            project=project,
            branch_name=branch_name,
            tag_name=tag_name,
            tag_message=json_dumps(parameters),
            product_name=product_name,
        )

        workcopy_project_id = await vc_repo.get_workcopy_project_id(repo_id, commit_id)

        runnable_project_ids.append(ProjectID(workcopy_project_id))
        runnable_project_vc_commits.append(commit_id)

    return runnable_project_ids, runnable_project_vc_commits


async def get_runnable_projects_ids(
    request: web.Request,
    project_uuid: ProjectID,
) -> list[ProjectID]:
    vc_repo = VersionControlForMetaModeling.create_from_request(request)
    assert vc_repo.user_id  # nosec

    project: ProjectDict = await vc_repo.get_project(str(project_uuid))
    assert project["uuid"] == str(project_uuid)  # nosec
    project_nodes: dict[NodeID, Node] = {
        nid: Node.model_validate(n) for nid, n in project["workbench"].items()
    }

    # init returns
    runnable_project_ids: list[ProjectID] = []

    # std-project
    is_meta_project = any(
        is_iterator_service(node.key) for node in project_nodes.values()
    )
    if not is_meta_project:
        runnable_project_ids.append(project_uuid)
        return runnable_project_ids

    raise NotImplementedError
    # SEE https://github.com/ITISFoundation/osparc-simcore/issues/2735
