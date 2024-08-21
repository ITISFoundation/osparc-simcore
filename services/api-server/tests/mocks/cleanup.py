import argparse
import json
import re
from pathlib import Path

from faker import Faker

_fake = Faker()


def anonymize_values(json_key, json_data):
    if isinstance(json_data, dict):
        for key, value in json_data.items():
            json_data[key] = anonymize_values(key, value)
    elif isinstance(json_data, list):
        for i in range(len(json_data)):
            json_data[i] = anonymize_values(i, json_data[i])
    elif isinstance(json_data, str):
        if "@" in json_data:
            print("\tAnonymizing email ...")
            json_data = _fake.email()
        elif json_key == "affiliation":
            print(f"\tAnonymizing {json_key} ...")
            json_data = _fake.company()
        elif json_key == "name" and re.match(r"^[A-Z][a-z]+ +[A-Z][a-z]+$", json_data):
            print("\tAnonymizing user names ...")
            json_data = f"{_fake.first_name()} {_fake.last_name()}"

    return json_data


def main():
    parser = argparse.ArgumentParser(description="Anonymizes mocks/*.json files")

    parser.add_argument(
        "file", nargs="?", type=str, help="The file that will be sanitized"
    )
    args = parser.parse_args()

    if args.file:
        target = Path(args.file)
        assert target.exists()
        iter_paths = [
            target,
        ]
    else:
        iter_paths = Path.cwd().glob("*.json")

    for path in iter_paths:
        print("Anonymizing", path, "...")
        json_data = anonymize_values(None, json.loads(path.read_text()))
        path.write_text(json.dumps(json_data, indent=1))


if __name__ == "__main__":
    main()
