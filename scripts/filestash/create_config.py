"""
Parses the configuration template and injects it where the platform expects it
Notes:
- Admin credentials for filestash are admin:adminadmin
- $ must be escaped with $$ in the template file
"""

import os
import random
import string
import tempfile
from pathlib import Path
from string import Template

SCRIPT_DIR = Path(__file__).resolve().parent
TEMPLATE_PATH = SCRIPT_DIR / "filestash_config.json.template"
CONFIG_JSON = Path(tempfile.mkdtemp()) / "filestash_config.json"


# The distutils package has been deprecated in Python 3.10, so I copied the
# strtobool function from the distutils.util module.
def strtobool(val):
    """Convert a string representation of truth to true (1) or false (0).
    True values are 'y', 'yes', 't', 'true', 'on', and '1'; false values
    are 'n', 'no', 'f', 'false', 'off', and '0'.  Raises ValueError if
    'val' is anything else.
    """
    val = val.lower()
    if val in ("y", "yes", "t", "true", "on", "1"):
        return 1
    elif val in ("n", "no", "f", "false", "off", "0"):
        return 0
    else:
        raise ValueError(f"invalid truth value {val}")


def random_secret_key(length: int = 16) -> str:
    return "".join(random.choice(string.ascii_letters) for _ in range(length))


def patch_env_vars() -> None:
    endpoint = os.environ["S3_ENDPOINT"]
    if not endpoint.startswith("http"):
        protocol = "https" if strtobool(os.environ["S3_SECURE"].lower()) else "http"
        endpoint = f"{protocol}://{endpoint}"

    os.environ["S3_ENDPOINT"] = endpoint

    os.environ["REPLACE_SECRET_KEY"] = random_secret_key()


def main() -> None:
    patch_env_vars()

    assert TEMPLATE_PATH.exists()

    template_content = TEMPLATE_PATH.read_text()

    config_json = Template(template_content).substitute(os.environ)

    assert CONFIG_JSON.parent.exists()
    CONFIG_JSON.write_text(config_json)

    # path of configuration file is exported as env var
    print(f"{CONFIG_JSON}")


if __name__ == "__main__":
    main()
