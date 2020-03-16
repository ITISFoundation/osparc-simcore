import json
from pathlib import Path
from typing import Dict

from aiohttp import ClientSession
from jsonschema import ValidationError
from yarl import URL

from .jsonschema_validation import validate_instance


def _load_from_path(filepath: Path) -> Dict:
    with filepath.open() as f:
        spec_dict = json.load(f)
        return spec_dict


async def _load_from_url(session: ClientSession, url: URL) -> Dict:
    async with session.get(url) as resp:
        text = await resp.text()
        spec_dict = json.loads(text)
        return spec_dict


async def create_jsonschema_specs(
    location: Path, session: ClientSession = None
) -> Dict:
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
        spec_dict = await _load_from_url(session, URL(location))
    else:
        path = Path(location).expanduser().resolve()  # pylint: disable=no-member
        spec_dict = _load_from_path(path)

    try:
        # will throw a SchemaError if the schema is bad.
        # FIXME: validate_instance in this case logs an error when raising the exception! TMP patched adding log_errors flag
        validate_instance(None, spec_dict, log_errors=False)
    except ValidationError:
        # no instance provided so it makes sense for a valid schema
        pass

    return spec_dict
