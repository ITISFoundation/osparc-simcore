from .models import DagTemplate


def validate_dag(template: DagTemplate) -> None:
    # Placeholder: validate nodes referenced by edges exist + detect cycles
    _ = template


def reverse_subdag(template: DagTemplate, *, nodes_subset: set[str], workflow_id: str) -> DagTemplate:
    reversed_edges: set[tuple[str, str]] = set()
    for depends_on, step in template.edges:
        if depends_on in nodes_subset and step in nodes_subset:
            reversed_edges.add((step, depends_on))
    return DagTemplate(workflow_id=workflow_id, nodes=set(nodes_subset), edges=reversed_edges)
