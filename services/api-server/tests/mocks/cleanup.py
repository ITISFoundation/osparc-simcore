import json
import re
from pathlib import Path

from faker import Faker

_fake = Faker()


def replace_with_fake(json_key, json_data):
    if isinstance(json_data, dict):
        for key, value in json_data.items():
            json_data[key] = replace_with_fake(key, value)
    elif isinstance(json_data, list):
        for i in range(len(json_data)):
            json_data[i] = replace_with_fake(i, json_data[i])
    elif isinstance(json_data, str):
        if "@" in json_data:
            json_data = _fake.email()
        elif json_key == "affiliation":
            json_data = _fake.company()
        elif json_key == "name" and re.match(r"^[A-Z][a-z]+ [A-Z][a-z]+$", json_data):
            json_data = f"{_fake.first_name()} {_fake.last_name()}"

    return json_data


def main():
    for path in Path.cwd().glob("*.json"):
        json_data = replace_with_fake(None, json.loads(path.read_text()))
        path.write_text(json.dumps(json_data, indent=1))


if __name__ == "__main__":
    main()
