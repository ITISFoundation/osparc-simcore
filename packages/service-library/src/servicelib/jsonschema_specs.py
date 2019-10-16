import json
from pathlib import Path
from typing import Dict, Optional

from aiohttp import ClientSession
from jsonschema import ValidationError
from yarl import URL

from .jsonschema_validation import validate_instance
from .utils import resolve_location


def load_specs_from_path(filepath: Path) -> Dict:
    with filepath.open() as f:
        spec_dict = json.load(f)
        return spec_dict

async def load_specs_from_url(session: ClientSession, url: URL) -> Dict:
    async with session.get(url) as resp:
        text = await resp.text()
        spec_dict = json.loads(text)
        return spec_dict

async def create_jsonschema_specs(location, session: Optional[ClientSession]=None) -> Dict:
    """ Loads specs from a given location (url or path),
        validates them and returns a working instance

    If location is an url, the specs are loaded asyncronously

    Both location types (url and file) are intentionally managed
    by the same function call to enforce developer always supporting
    both options. Notice that the url location enforces
    the consumer context to be asyncronous.
    """
    loc = resolve_location(location)

    if isinstance(loc, URL):
        if session is None:
            raise ValueError("Client session required in arguments")

        spec_dict = await load_specs_from_url(session, loc)
    else:
        assert isinstance(loc, Path)
        spec_dict = load_specs_from_path(loc)

    try:
        # will throw a SchemaError if the schema is bad.
        # FIXME: validate_instance in this case logs an error when raising the exception! TMP patched adding log_errors flag
        validate_instance(None, spec_dict, log_errors=False)
    except ValidationError:
        # no instance provided so it makes sense for a valid schema
        pass

    return spec_dict
