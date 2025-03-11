import ast
import json
from pathlib import Path

import astor


def update_messages_in_code(code_file, messages_file):
    # Load corrected messages from the JSON file
    with Path.open(messages_file) as f:
        corrected_messages = json.load(f)

    # Parse the Python code
    with Path.open(code_file) as f:
        tree = ast.parse(f.read())

    # Walk through the AST to find calls to `mark_for_review`
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and getattr(node.func, "id", None) == "mark_for_review"
        ):
            # Get the original message
            if isinstance(node.args[0], ast.Constant):
                original_message = node.args[0].value

                # Match it with corrected messages
                for key, corrected_message in corrected_messages.items():
                    if original_message == corrected_message["original"]:
                        # Replace the message with the corrected version
                        node.args[0].value = corrected_message["current"]

                        # Add the version as the second argument
                        version_node = ast.Constant(value=corrected_message["version"])
                        if len(node.args) == 1:
                            node.args.append(version_node)
                        else:
                            node.args[1] = version_node

    # Write the updated code back to the file
    updated_code = astor.to_source(tree)
    with Path.open(code_file, "w") as f:
        f.write(updated_code)
