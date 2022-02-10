"""
Parses the configuration template and injects it where the platform expects it
Notes:
- Admin credentials for filestash are admin:adminadmin
- $ must be escaped with $$ in the teemplate file
"""

import os

from pathlib import Path
from string import Template

SCRIPT_DIR = Path(__file__).absolute().parent
TEMPLATE_PATH = SCRIPT_DIR / "filestash_config.json.template"
CONFIG_TEMP_DIR = SCRIPT_DIR / ".." / ".." / "_tmp"
CONFIG_JSON = CONFIG_TEMP_DIR / "filestash_config.json"


def patch_env_vars() -> None:
    endpoint = os.environ["S3_ENDPOINT"]
    if not endpoint.startswith("http"):
        endpoint = f"http://{endpoint}"

    os.environ["S3_ENDPOINT"] = endpoint


def main() -> None:
    patch_env_vars()

    assert TEMPLATE_PATH.exists()

    template_content = TEMPLATE_PATH.read_text()

    config_json = Template(template_content).substitute(os.environ)

    CONFIG_TEMP_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_JSON.write_text(config_json)


if __name__ == "__main__":
    main()
