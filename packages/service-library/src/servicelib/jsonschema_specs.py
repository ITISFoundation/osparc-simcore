import json
from pathlib import Path
from typing import Dict
from .jsonschema_validation import validate_instance


from aiohttp import ClientSession
from jsonschema import ValidationError
from yarl import URL


def _load_from_path(filepath: Path) -> Dict:
    with filepath.open() as f:
        spec_dict = json.load(f)
        return spec_dict


async def _load_from_url(url: URL) -> Dict:
    async with ClientSession() as session:
        async with session.get(url) as resp:
            text = await resp.text()
            spec_dict = json.loads(text)
            return spec_dict

async def create_jsonschema_specs(location: Path) -> Dict:
    """ Loads specs from a given location (url or path),
        validates them and returns a working instance

    If location is an url, the specs are loaded asyncronously

    Both location types (url and file) are intentionally managed
    by the same function call to enforce developer always supporting
    both options. Notice that the url location enforces
    the consumer context to be asyncronous.

    :param location: url or path
    :return: validated jsonschema specifications object
    :rtype: Dict
    """
    if URL(str(location)).host:
        spec_dict = await _load_from_url(URL(location))
    else:
        path = Path(location).expanduser().resolve() #pylint: disable=no-member
        spec_dict = _load_from_path(path)

    try:
        # will throw a SchemaError if the schema is bad.
        validate_instance(None, spec_dict)
    except ValidationError:
        # no instance provided so it makes sense for a valid schema
        pass

    return spec_dict
