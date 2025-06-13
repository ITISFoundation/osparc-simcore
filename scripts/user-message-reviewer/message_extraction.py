import ast
import json
from pathlib import Path

"""
def mark_for_review(message):
    return message

# Example error messages
error_message = mark_for_review("Invalid input: '{input_value}'")
not_found_message = mark_for_review("File '{filename}' was not found")
"""


def extract_unreviewed_messages(code_file, output_file, condition=None):
    """
    Extracts messages from mark_for_review calls that match a condition on the version tag.

    Parameters:
        code_file (str): Path to the Python source code file.
        output_file (str): Path to save the extracted messages as a JSON file.
        condition (callable, optional): A function to evaluate the version tag. If None, extracts messages with no version tag.
    """
    with Path.open(code_file) as f:
        tree = ast.parse(f.read())

    messages = {}

    # Walk through the AST to find calls to `mark_for_review`
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and getattr(node.func, "id", None) == "mark_for_review"
        ):
            if len(node.args) >= 1 and isinstance(node.args[0], ast.Constant):
                original_message = node.args[0].value
                version = None

                # Check if a second argument (version) exists
                if len(node.args) > 1 and isinstance(node.args[1], ast.Constant):
                    version = node.args[1].value

                # Apply the filter condition
                if condition is None or condition(version):
                    key = f"{node.lineno}_{node.col_offset}"  # Unique key based on location
                    messages[key] = {"message": original_message, "version": version}

    # Save extracted messages to a JSON file
    with Path.open(output_file, "w") as f:
        json.dump(messages, f, indent=4)


# Example usage
# Condition: Extract messages with no version or explicitly unreviewed (e.g., version is None or "unreviewed")
def is_unreviewed(version):
    return version is None or version == "unreviewed"


# extract_unreviewed_messages("your_script.py", "unreviewed_messages.json", condition=is_unreviewed)
