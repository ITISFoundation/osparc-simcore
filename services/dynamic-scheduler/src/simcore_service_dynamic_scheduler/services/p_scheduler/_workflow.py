import networkx as nx

from ._abc import BaseStep
from ._models import DagNodeUniqueReference, DagStepSequences, StepSequence, WorkflowDefinition, WorkflowName


def _get_step_sequence(definition: WorkflowDefinition) -> StepSequence:
    graph = nx.DiGraph()

    for step_type, requires_step_types in definition:
        graph.add_node(step_type.get_unique_reference())
        for requires in requires_step_types:
            graph.add_edge(requires.get_unique_reference(), step_type.get_unique_reference())

    if not nx.is_directed_acyclic_graph(graph):
        msg = "The provided workflow definition is not a DAG"
        raise ValueError(msg)

    return tuple(set(gen) for gen in nx.topological_generations(graph))


def _get_step_references_to_types(definition: WorkflowDefinition) -> dict[DagNodeUniqueReference, type[BaseStep]]:
    result: dict[DagNodeUniqueReference, type[BaseStep]] = {}
    for step_type, requires_step_types in definition:
        result[step_type.get_unique_reference()] = step_type

        for required_step_type in requires_step_types:
            result[required_step_type.get_unique_reference()] = required_step_type

    return result


class WorkflowManager:
    def __init__(self) -> None:
        self._workflows: dict[WorkflowName, WorkflowDefinition] = {}
        self._dag_step_sequences: dict[WorkflowName, DagStepSequences] = {}
        self._mapping_reference_to_base_step: dict[DagNodeUniqueReference, type[BaseStep]] = {}

    def register_workflow(self, name: WorkflowName, definition: WorkflowDefinition) -> None:
        self._workflows[name] = definition

    def get_workflow_step_sequences(self, name: WorkflowName) -> DagStepSequences:
        return self._dag_step_sequences[name]

    def get_base_step(self, dag_node_name: DagNodeUniqueReference) -> type[BaseStep]:
        return self._mapping_reference_to_base_step[dag_node_name]

    async def setup(self) -> None:
        # it takes a bit to compute the dag, precompute everything
        for name, definition in self._workflows.items():
            step_sequence = _get_step_sequence(definition)
            self._dag_step_sequences[name] = DagStepSequences(
                apply=step_sequence, revert=tuple(reversed(step_sequence))
            )

            mapping = _get_step_references_to_types(definition)
            for key in mapping:
                if key in self._mapping_reference_to_base_step:
                    msg = (
                        f"'{key}' already registered in {self._mapping_reference_to_base_step}. "
                        f"Ensure name of the {BaseStep.__class__.__name__} is unique."
                    )
                    raise ValueError(msg)

            self._mapping_reference_to_base_step.update(mapping)

    async def teardown(self) -> None:
        self._workflows.clear()
        self._dag_step_sequences.clear()
        self._mapping_reference_to_base_step.clear()
