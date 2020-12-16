import yaml

from typing import Dict

from aiohttp import web


def dumps(data: Dict) -> str:
    try:
        return yaml.safe_dump(data)
    except yaml.YAMLError:
        web.HTTPException(reason=f"Could not encode into YAML from '{data}'")


def loads(string_data: str) -> Dict:
    try:
        return yaml.safe_load(string_data)
    except yaml.YAMLError:
        web.HTTPException(reason=f"Could not decode YAML from '{string_data}'")
