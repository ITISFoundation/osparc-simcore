# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import itertools
from copy import deepcopy
from typing import Any, Callable, Dict, Iterator, List, Tuple
from uuid import UUID

import pytest
from faker import Faker
from models_library.frontend_services_catalog import (
    FRONTEND_SERVICE_KEY_PREFIX,
    _create_constant_node_def,
    _create_data_iterator_int_range,
    is_iterator_service,
    iter_service_docker_data,
)
from models_library.projects import Project
from models_library.projects_nodes import (
    InputID,
    InputTypes,
    Node,
    OutputID,
    OutputTypes,
)
from models_library.projects_nodes_io import NodeID, PortLink
from models_library.services import ServiceDockerData
from simcore_service_webserver.meta_core import PROPTYPE_2_PYTYPE, SumDiffDef

## HELPERS -------------------------------------------------


def _linspace_func(
    linspace_start: int = 0, linspace_stop: int = 1, linspace_step: int = 1
) -> Iterator[int]:
    for value in range(linspace_start, linspace_stop, linspace_step):
        yield value


def linspace_generator(**kwargs) -> Iterator[Dict[str, OutputTypes]]:
    # maps generator with iterable outputs. can have non-iterable outputs
    # as well
    for value in _linspace_func(**kwargs):
        yield {"out_1": value}


def sum_all(
    linspace_start: int = 0, linspace_stop: int = 1, linspace_step: int = 1
) -> int:
    return sum(range(linspace_start, linspace_stop, linspace_step))


def fake_input(
    value_type: str, default_value: Any, fake: Faker, *, prefer_default: bool = False
) -> InputTypes:
    # Produces a concrete value given metadata
    python_type = PROPTYPE_2_PYTYPE.get(value_type)
    if not python_type:
        raise NotImplementedError()

    if prefer_default and default_value:
        return python_type(default_value)

    faker_func = getattr(fake, f"py{python_type.__name__}")

    return faker_func()


def create_node_model(
    node_def: ServiceDockerData,
    node_inputs: Dict[InputID, InputTypes] = None,
    outputs: List[OutputTypes] = None,
) -> Node:
    node_def.inputs = node_def.inputs or {}
    node_def.outputs = node_def.outputs or {}

    node_inputs = node_inputs or {}

    # map and validate inputs
    for input_name, input_meta in node_def.inputs.items():
        if input_name not in node_inputs:
            node_inputs[input_name] = PROPTYPE_2_PYTYPE[input_meta.property_type](
                input_meta.default_value
            )

    # map and validate outputs
    outputs = outputs or []
    node_outputs: Dict[OutputID, OutputTypes] = {}

    if outputs:
        # setting outputs
        for output_index, (output_name, output_meta) in enumerate(
            node_def.outputs.items()
        ):
            value = outputs[output_index]
            try:
                python_type = PROPTYPE_2_PYTYPE[output_meta.property_type]
                node_outputs[output_name] = python_type(value)
            except KeyError:
                # it is a link or glob?
                pass
                # node_outputs[output_name] = ...

    # create (w/ validation)
    node_model: Node = Node(
        key=node_def.key,
        version=node_def.version,
        label=node_def.name,
        inputs=node_inputs,
        outputs=node_outputs,
        progress=0,
    )

    return node_model


def create_const_node(outputs: List[Tuple[OutputID, str, OutputTypes]]) -> Node:
    # FIXME:
    if len(outputs) != 1:
        raise NotImplementedError(
            "WIP: only implemented const-nodes with a single output"
        )

    oname, otype, ovalue = outputs[0]
    node = create_node_model(
        _create_constant_node_def(otype, oname),
        None,
        [
            ovalue,
        ],
    )

    assert node.outputs
    assert oname in node.outputs
    return node


SERVICES_CATALOG: Dict[Tuple[str, str], ServiceDockerData] = {
    SumDiffDef.info.unique_id: SumDiffDef.to_dockerdata(),
    **{(s.key, s.version): s for s in iter_service_docker_data()},
}

SERVICE_TO_CALLABLES: Dict[Tuple[str, str], Callable] = {
    # ensure inputs/outputs map function signature
    (
        f"{FRONTEND_SERVICE_KEY_PREFIX}/data-iterator/int-range",
        "1.0.0",
    ): linspace_generator,
    SumDiffDef.info.unique_id: SumDiffDef.run_with_model,
}


def search_by_key(key_sub, container: Dict):
    return next(s for k, s in container.items() if key_sub in k[0])


## FIXTURES -------------------------------------------------


@pytest.fixture
def project_nodes(faker: Faker) -> Dict[NodeID, Node]:
    nodes = {}

    # # node 0
    n0 = faker.uuid4()
    # nodes[n0] = node0 = create_node_model(
    #     node_def=search_by_key("int-range", SERVICES_CATALOG),
    #     node_inputs={"linspace_start": 0, "linspace_stop": 10},
    # )

    # # link
    # node0.outputs = node0.outputs or {}
    # output_name = next(iter(node0.outputs.keys()))
    # n0o0 = PortLink(nodeUUID=n0, output=output_name)

    # # node 1
    n1 = faker.uuid4()
    # nodes[n1] = node1 = create_node_model(
    #     node_def=search_by_key(SumDiffDef.info.key, SERVICES_CATALOG),
    #     node_inputs={"x": n0o0, "y": 10},
    # )
    # node1.input_nodes = [
    #     n0,
    # ]

    nodes[n0] = node0 = Node.parse_obj(
        {
            "key": "simcore/services/frontend/data-iterator/int-range",
            "version": "1.0.0",
            "label": "iter",
            "inputs": {"linspace_start": 0, "linspace_stop": 10, "linspace_step": 1},
        }
    )

    nodes[n1] = Node.parse_obj(
        {
            "key": "simcore/services/frontend/def/sum_diff",
            "version": "1.0.0",
            "label": "sum_diff",
            "inputs": {"x": PortLink(nodeUuid=n0, output="out_1"), "y": 10},
        }
    )

    return nodes


## TESTS -------------------------------------------------


def test_it(project_nodes: Dict[NodeID, Node]):

    # select iterable nodes
    iterable_nodes_defs: List[ServiceDockerData] = []  # schemas of iterable nodes
    iterable_nodes: List[Node] = []  # iterable nodes
    iterable_nodes_ids: List[UUID] = []

    for node_id, node in project_nodes.items():
        if is_iterator_service(node.key):
            node_def = SERVICES_CATALOG[(node.key, node.version)]
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
        g = node_call(**{name: node.inputs[name] for name in node_def.inputs})
        assert isinstance(g, Iterator)
        nodes_generators.append(g)

    # generate values
    for parameters in itertools.product(*nodes_generators):
        # Q: what if iter are infinite?
        # Q: preview & crop iterations?

        node_results: Dict[OutputID, OutputTypes]

        iter_project_nodes = deepcopy(project_nodes)

        for node_results, node_def, node_id in zip(
            parameters, iterable_nodes_defs, iterable_nodes_ids
        ):

            assert node_def.outputs
            assert 1 <= len(node_results) <= len(node_def.outputs)

            # override outputs of corresponding iter
            iter_node = iter_project_nodes[node_id]
            iter_node.outputs = iter_node.outputs or {}
            for output_key, output_value in node_results.items():
                iter_node.outputs[output_key] = output_value

        print(node_results, "->")
        for nid in iter_project_nodes:
            print(nid)
            print(iter_project_nodes[nid].json(indent=2))

        # pack as const-nodes
        # const_nodes: List[Node] = []

        # for node_results, node_def in zip(results, iterable_nodes_defs):

        #     assert node_def.outputs
        #     assert len(node_def.outputs) == len(node_results)

        #     outs = []
        #     for output_name in node_def.outputs:
        #         output_type = node_def.outputs[output_name].property_type
        #         output_value = node_results[output_name]
        #         outs.append(tuple([output_name, output_type, output_value]))

        #     # create const-nodes
        #     const_node: Node = create_const_node(outs)
        #     const_nodes.append(const_node)

        #     # replace iterable nodes by const-nodes
        #     iteration_project_nodes = {
        #         k: deepcopy(v)
        #         for k, v in project_nodes.items()
        #         if k not in iterable_nodes_ids
        #     }

        #     assert set(iterable_nodes) == set(const_nodes)
        #     iteration_project_nodes.update(zip(iterable_nodes_ids, const_nodes))

        #     print(results, "->", iteration_project_nodes)


@pytest.mark.skip(reason="DEV")
def test_that(faker: Faker):

    # define schema of a service
    #   - i/o signatures
    #
    node_def: ServiceDockerData = _create_data_iterator_int_range()

    # FIXME: must be {}
    node_def.inputs = node_def.inputs or {}
    node_def.outputs = node_def.outputs or {}

    # defines implementation -------
    node_run: Callable = sum_all

    # user creates node instance -------

    # set inputs
    node_inputs: Dict[InputID, InputTypes] = {}

    for input_name, input_meta in node_def.inputs.items():
        node_inputs[input_name] = fake_input(
            input_meta.property_type, input_meta.default_value, faker
        )

    # create (w/ validation)
    node_model: Node = Node(
        key=node_def.key,
        version=node_def.version,
        label=node_def.name,
        inputs=node_inputs,
        outputs={},  # still did not run
        progress=0,
    )

    # RUN node instance
    assert node_model.inputs
    outputs = node_run(**node_model.inputs)

    # COLLECT results
    # map outputs
    node_outputs: Dict[OutputID, OutputTypes] = {}

    # These are expected outputs, parse, validate and assign
    if node_def.outputs:
        if len(node_def.outputs) == 1:
            outputs = [
                outputs,
            ]

        assert isinstance(outputs, list)
        for output_index, (output_name, output_meta) in enumerate(
            node_def.outputs.items()
        ):
            value = outputs[output_index]
            try:
                python_type = PROPTYPE_2_PYTYPE[output_meta.property_type]
                node_outputs[output_name] = python_type(value)
            except KeyError:
                # it is a link or glob?
                pass
                # node_outputs[output_name] = ...

    node_model.outputs = node_outputs

    print(node_model)


@pytest.mark.skip(reason="DEV")
def test_prepro_meta_project(meta_project: Project):

    iter_nodes = []
    project_instances = []
    for variants in itertools.product(*iter_nodes):
        project = meta_project.copy()
        for v in variants:
            project.workbench[v.key] = v.node()

        project_instances.append(project)
