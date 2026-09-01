from models_library.api_schemas_webserver.projects_nodes import NodePatch
from models_library.projects_nodes_io import PortLink


def test_node_patch_to_domain_model_preserves_input_types():
    literal_input = {
        "kind": "metadata",
        "nodeUuid": "11111111-1111-4111-8111-111111111111",
    }
    node_patch = NodePatch.model_validate(
        {
            "inputs": {
                "link": {
                    "nodeUuid": "22222222-2222-4222-8222-222222222222",
                    "output": "out_1",
                },
                "literal": literal_input,
                "scalar": 42,
            }
        }
    )

    partial_node = node_patch.to_domain_model()

    assert partial_node.inputs is not None
    assert isinstance(partial_node.inputs["link"], PortLink)
    assert partial_node.inputs["literal"] == literal_input
    assert partial_node.inputs["scalar"] == 42
    assert partial_node.model_fields_set == {"inputs"}
