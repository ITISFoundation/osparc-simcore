import json
import re
from pathlib import Path

from faker import Faker

_fake = Faker()


def obfuscate_values(json_key, json_data):
    if isinstance(json_data, dict):
        for key, value in json_data.items():
            json_data[key] = obfuscate_values(key, value)
    elif isinstance(json_data, list):
        for i in range(len(json_data)):
            json_data[i] = obfuscate_values(i, json_data[i])
    elif isinstance(json_data, str):
        if "@" in json_data:
            json_data = _fake.email()
        elif json_key == "affiliation":
            json_data = _fake.company()
        elif json_key == "name" and re.match(r"^[A-Z][a-z]+ +[A-Z][a-z]+$", json_data):
            json_data = f"{_fake.first_name()} {_fake.last_name()}"

    return json_data


def main():
    for path in Path.cwd().glob("*.json"):
        json_data = obfuscate_values(None, json.loads(path.read_text()))
        path.write_text(json.dumps(json_data, indent=1))


if __name__ == "__main__":
    main()
