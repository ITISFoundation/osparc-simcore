import networkx as nx

from ._models import DagStepSequences, StepSequence, WorkflowDefinition, WorkflowName


def _get_step_sequence(definition: WorkflowDefinition) -> StepSequence:
    graph = nx.DiGraph()

    for step_type, step_type_requires in definition:
        graph.add_node(step_type)
        for requires in step_type_requires:
            graph.add_edge(requires, step_type)

    if not nx.is_directed_acyclic_graph(graph):
        msg = "The provided workflow definition is not a DAG"
        raise ValueError(msg)

    return tuple(set(gen) for gen in nx.topological_generations(graph))


class DagManager:
    def __init__(self) -> None:
        self._workflows: dict[WorkflowName, WorkflowDefinition] = {}
        self._dag_step_sequences: dict[WorkflowName, DagStepSequences] = {}

    def register_workflow(self, name: WorkflowName, definition: WorkflowDefinition) -> None:
        self._workflows[name] = definition

    def get_workflow_step_sequences(self, name: WorkflowName) -> DagStepSequences:
        return self._dag_step_sequences[name]

    async def setup(self) -> None:
        # it takes a bit to compute the dags
        for name, definition in self._workflows.items():
            step_sequence = _get_step_sequence(definition)
            self._dag_step_sequences[name] = DagStepSequences(
                apply=step_sequence, revert=tuple(reversed(step_sequence))
            )

    async def teardown(self) -> None:
        self._workflows.clear()
        self._dag_step_sequences.clear()
