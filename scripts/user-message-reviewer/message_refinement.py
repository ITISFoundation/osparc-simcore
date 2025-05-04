import json
import os
from pathlib import Path

import openai

# Set your OpenAI API key
openai.api_key = os.environ["OPENAPI_API_KEY"]


def load_rules(rules_file):
    """Load rules for message refinement from a JSON file."""
    with Path.open(rules_file) as f:
        return json.load(f)


def load_messages(messages_file):
    """Load messages from the messages.json file."""
    with Path.open(messages_file) as f:
        return json.load(f)


def send_to_chatgpt(messages, rules):
    """Send messages and rules to ChatGPT and request alternatives."""
    refined_messages = {}
    for key, details in messages.items():
        message = details["message"]
        version = details.get("version", "unknown")

        # Prepare the prompt
        prompt = f"""
You are a language expert. Apply the following rules to suggest alternatives for the given message:

Rules:
- Tone: {rules['tone']}
- Style: {rules['style']}
- Length: {rules['length']}
- Placeholders: {rules['placeholders']}

Original Message: "{message}"

Provide three alternatives based on the above rules. Ensure placeholders remain intact.
"""

        # Send the request to ChatGPT
        response = openai.Completion.create(
            engine="text-davinci-003", prompt=prompt, max_tokens=150, temperature=0.7
        )

        # Parse the response
        alternatives = response.choices[0].text.strip()
        refined_messages[key] = {
            "original": message,
            "version": version,
            "alternatives": alternatives.split(
                "\n"
            ),  # Split into list if alternatives are on separate lines
        }

    return refined_messages


def save_refined_messages(output_file, refined_messages):
    """Save the refined messages to a JSON file."""
    with Path.open(output_file, "w") as f:
        json.dump(refined_messages, f, indent=4)


# Example usage
# update_messages_in_code("your_script.py", "messages.json")


# Main script
if __name__ == "__main__":
    # File paths
    messages_file = "messages.json"
    rules_file = "rules.json"
    output_file = "refined_messages.json"

    # Load inputs
    rules = load_rules(rules_file)
    messages = load_messages(messages_file)

    # Process messages with ChatGPT
    refined_messages = send_to_chatgpt(messages, rules)

    # Save the refined messages
    save_refined_messages(output_file, refined_messages)

    print(f"Refined messages saved to {output_file}.")
