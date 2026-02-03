import itertools

import networkx as nx
from servicelib.fastapi.app_state import SingletonInAppStateMixin

from ._abc import BaseStep, InDataKeys
from ._models import DagNodeUniqueReference, KeyConfig, StepSequence, WorkflowDefinition, WorkflowName


def _get_step_sequence(definition: WorkflowDefinition) -> StepSequence:
    graph = nx.DiGraph()

    for step_type, requires_step_types in definition.steps:
        graph.add_node(step_type.get_unique_reference())
        for requires in requires_step_types:
            graph.add_edge(requires.get_unique_reference(), step_type.get_unique_reference())

    if not nx.is_directed_acyclic_graph(graph):
        msg = "The provided workflow definition is not a DAG"
        raise ValueError(msg)

    return tuple(set(gen) for gen in nx.topological_generations(graph))


def _get_step_references_to_types(definition: WorkflowDefinition) -> dict[DagNodeUniqueReference, type[BaseStep]]:
    result: dict[DagNodeUniqueReference, type[BaseStep]] = {}
    for step_type, requires_step_types in definition.steps:
        result[step_type.get_unique_reference()] = step_type

        for required_step_type in requires_step_types:
            result[required_step_type.get_unique_reference()] = required_step_type

    return result


def _check_no_parallel_steps_write_same_key(
    step_sequences: StepSequence, step_references_to_types: dict[DagNodeUniqueReference, type[BaseStep]], *, phase: str
) -> None:
    for step_sequence in step_sequences:
        current_outputs: set[str] = set()
        for step in step_sequence:
            step_class = step_references_to_types[step]
            outputs = step_class.apply_provides_outputs() if phase == "APPLY" else step_class.revert_provides_outputs()
            for key_config in outputs:
                if key_config.name in current_outputs:
                    msg = (
                        f"'{step=}' in parallel execution produces output key '{key_config.name}' "
                        f"already added by a step in {phase} sequence: {step_sequence=}"
                    )
                    raise ValueError(msg)
                current_outputs.add(key_config.name)


def _check_requests_inputs_present(
    in_data_keys: InDataKeys, step: DagNodeUniqueReference, sequence_context: set[str], *, phase: str
) -> None:
    for key_config in in_data_keys:
        if key_config.name not in sequence_context and key_config.optional is False:
            msg = f"{step=} requires input key '{key_config.name}' not present in {phase} {sequence_context=}"
            raise ValueError(msg)


def _validate_step_sequences(
    step_sequence: StepSequence,
    step_references_to_types: dict[DagNodeUniqueReference, type[BaseStep]],
    initial_context: set[KeyConfig],
) -> None:
    _check_no_parallel_steps_write_same_key(step_sequence, step_references_to_types, phase="APPLY")
    _check_no_parallel_steps_write_same_key(step_sequence, step_references_to_types, phase="REVERT")

    sequence_context: set[str] = set()
    for key_config in initial_context:
        if key_config.optional is True:
            msg = f"Initial context cannot have optional keys: {key_config=}"
            raise ValueError(msg)
        sequence_context.add(key_config.name)

    # check apply key sequence
    for sequence in step_sequence:
        sequence_output_keys: set[str] = set()
        for step in sequence:
            step_class = step_references_to_types[step]

            _check_requests_inputs_present(step_class.apply_requests_inputs(), step, sequence_context, phase="APPLY")
            _check_requests_inputs_present(step_class.revert_requests_inputs(), step, sequence_context, phase="REVERT")

            # add APPLY and REVERT outputs
            for key_config in itertools.chain(
                step_class.apply_provides_outputs(), step_class.revert_provides_outputs()
            ):
                sequence_output_keys.add(key_config.name)
        sequence_context.update(sequence_output_keys)


class WorkflowManager(SingletonInAppStateMixin):
    app_state_name: str = "p_scheduler_workflow_manager"

    def __init__(self) -> None:
        self._workflows: dict[WorkflowName, WorkflowDefinition] = {}
        self._dag_step_sequences: dict[WorkflowName, StepSequence] = {}
        self._mapping_step_references_to_types: dict[DagNodeUniqueReference, type[BaseStep]] = {}

    def register_workflow(self, name: WorkflowName, definition: WorkflowDefinition) -> None:
        self._workflows[name] = definition

    def get_workflow_step_sequences(self, name: WorkflowName) -> StepSequence:
        return self._dag_step_sequences[name]

    def get_base_step(self, dag_node_name: DagNodeUniqueReference) -> type[BaseStep]:
        return self._mapping_step_references_to_types[dag_node_name]

    async def setup(self) -> None:
        for name, definition in self._workflows.items():
            step_references_to_types = _get_step_references_to_types(definition)
            step_sequence = _get_step_sequence(definition)

            for key in step_references_to_types:
                if key in self._mapping_step_references_to_types:
                    msg = (
                        f"{key=} already registered in {self._mapping_step_references_to_types}. "
                        f"Ensure name of the {BaseStep.__class__.__name__} is unique."
                    )
                    raise ValueError(msg)
            _validate_step_sequences(step_sequence, step_references_to_types, definition.initial_context)

            self._dag_step_sequences[name] = step_sequence
            self._mapping_step_references_to_types.update(step_references_to_types)

    async def teardown(self) -> None:
        self._workflows.clear()
        self._dag_step_sequences.clear()
        self._mapping_step_references_to_types.clear()
