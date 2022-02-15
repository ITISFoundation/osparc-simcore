"""
Parses the configuration template and injects it where the platform expects it
Notes:
- Admin credentials for filestash are admin:adminadmin
- $ must be escaped with $$ in the teemplate file
"""

import os
import tempfile

from distutils.util import strtobool
from pathlib import Path
from string import Template

SCRIPT_DIR = Path(__file__).resolve().parent
TEMPLATE_PATH = SCRIPT_DIR / "filestash_config.json.template"
CONFIG_JSON = Path(tempfile.mkdtemp()) / "filestash_config.json"


def patch_env_vars() -> None:
    endpoint = os.environ["S3_ENDPOINT"]
    if not endpoint.startswith("http"):
        protocol = "https" if strtobool(os.environ["S3_SECURE"].lower()) else "http"
        endpoint = f"{protocol}://{endpoint}"

    os.environ["S3_ENDPOINT"] = endpoint


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
