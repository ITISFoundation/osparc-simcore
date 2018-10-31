import yaml

from .resources import resources
from .settings import OAS_ROOT_FILE


def api_version() -> str:
    specs = yaml.load(resources.stream(OAS_ROOT_FILE))
    return specs['info']['version']
