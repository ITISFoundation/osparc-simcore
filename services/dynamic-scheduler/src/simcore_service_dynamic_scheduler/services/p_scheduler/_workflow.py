from copy import deepcopy

import networkx as nx

from ._abc import BaseStep
from ._models import DagNodeUniqueReference, DagStepSequences, KeyConfig, StepSequence, WorkflowDefinition, WorkflowName


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
    step_sequences: StepSequence, mapping: dict[DagNodeUniqueReference, type[BaseStep]], *, phase: str
) -> None:
    for step_sequence in step_sequences:
        current_outputs: set[str] = set()
        for step in step_sequence:
            step_class = mapping[step]
            outputs = step_class.apply_provides_outputs() if phase == "apply" else step_class.revert_provides_outputs()
            for key_config in outputs:
                if key_config.name in current_outputs:
                    msg = (
                        f"'{step=}' in parallel execution produces output key '{key_config.name}' that is "
                        f"already produced by another step in the same {phase} sequence: {step_sequence=}"
                    )
                    raise ValueError(msg)
                current_outputs.add(key_config.name)


def _validate_step_sequences(
    dag_step_sequences: DagStepSequences,
    mapping: dict[DagNodeUniqueReference, type[BaseStep]],
    initial_context: set[KeyConfig],
) -> None:
    _check_no_parallel_steps_write_same_key(dag_step_sequences.apply, mapping, phase="apply")
    _check_no_parallel_steps_write_same_key(dag_step_sequences.revert, mapping, phase="revert")

    detected_input_keys: set[str] = {key_config.name for key_config in initial_context}
    sequence_minimum_keys: dict[int, set[str]] = {}

    # check that all requered inputs are present for every step in apply
    for k, step_sequence in enumerate(dag_step_sequences.apply):
        # the minuimum keys can be the ones before the step provided outputs
        sequence_minimum_keys[k] = deepcopy(detected_input_keys)

        for step in step_sequence:
            step_class = mapping[step]
            step_inputs = step_class.apply_requests_inputs()
            for key_config in step_inputs:
                if key_config.name not in detected_input_keys and not key_config.optional:
                    msg = (
                        f"'{step=}' requires input key '{key_config.name}' that is not provided by any previous "
                        f"step or the initial context: {detected_input_keys=}"
                    )
                    raise ValueError(msg)

                detected_input_keys.add(key_config.name)

    # check that all requered inputs are present for every step in revert
    # worst case scenario is considered here, these are the keys that do not exist beofe the apply counterpart ran
    for k, step_sequence in enumerate(dag_step_sequences.revert):
        minimum_keys = sequence_minimum_keys[k]
        for step in step_sequence:
            step_class = mapping[step]
            step_inputs = step_class.revert_requests_inputs()
            for key_config in step_inputs:
                if key_config.name not in minimum_keys and not key_config.optional:
                    msg = (
                        f"'{step=}' requires input key '{key_config.name}' that is not provided by any previous "
                        f"step or in the: {minimum_keys=}"
                    )
                    raise ValueError(msg)


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
            mapping = _get_step_references_to_types(definition)
            step_sequence = _get_step_sequence(definition)
            dag_step_sequences = DagStepSequences(apply=step_sequence, revert=tuple(reversed(step_sequence)))

            for key in mapping:
                if key in self._mapping_reference_to_base_step:
                    msg = (
                        f"'{key}' already registered in {self._mapping_reference_to_base_step}. "
                        f"Ensure name of the {BaseStep.__class__.__name__} is unique."
                    )
                    raise ValueError(msg)
            _validate_step_sequences(dag_step_sequences, mapping, definition.initial_context)

            self._dag_step_sequences[name] = dag_step_sequences
            self._mapping_reference_to_base_step.update(mapping)

    async def teardown(self) -> None:
        self._workflows.clear()
        self._dag_step_sequences.clear()
        self._mapping_reference_to_base_step.clear()
