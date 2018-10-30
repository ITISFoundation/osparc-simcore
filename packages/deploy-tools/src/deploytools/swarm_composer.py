import re
from collections import defaultdict
from copy import deepcopy
from functools import lru_cache
from typing import Dict, List, Optional
from pathlib import Path

from .merge import merge_docker_compose
from .readers import load_devel_environ, load_docker_compose
from .utils import dump_to_file, dump_to_stdout, output_dir


# SWARM OPTIONS ------------
@lru_cache(None)
def get_constraints() -> Dict:
    # TODO: check that these constraints are correct
    _constraints = defaultdict.fromkeys(["director", "webserver"],
        ['node.platform.os == linux', "node.role == manager"])
    _constraints.default_factory = list

    _constraints["apihub"].append('node.platform.os == linux')
    return _constraints

#-------------------------------



def resolve_environs(service_environ: List[str]) -> Dict:
    """ Creates a dict with the environment variables
        inside of a webserver container
    """
    host_environ = load_devel_environ()

    container_environ = {
       # 'SIMCORE_WEB_OUTDIR': 'home/scu/services/web/client' # defined in Dockerfile
    }

    MATCH = re.compile(r'\$\{(\w+)+')

    for item in service_environ:
        key, value = item.split("=")
        m = MATCH.match(value)
        if m:
            envkey = m.groups()[0]
            value = host_environ[envkey]
        container_environ[key] = value

    return container_environ



def resolve_deploy(dc_source: Dict, exclude: Optional[List[str]]=None) -> Dict:

    constraints = get_constraints()
    if exclude is None:
        exclude = []

    dc_deploy = deepcopy(dc_source)

    for name in dc_source["services"]:
        service = dc_deploy["services"][name]
        if name in exclude:
            dc_deploy["services"].pop(name)
            continue

        # remove builds
        service.pop("build", None)

        # replace by image
        service.setdefault("image", "services_{}:latest".format(name))

        # add deploy info
        constraint = constraints.get(name, None)
        if constraint is not None:
            service["deploy"] = {
                "placement": {
                    "constraints": list(constraint)
                }
            }

        # resolve environs
        if "environment" in service:
            environs = resolve_environs(service["environment"])
            service["environment"] = [ "{}={}".format(k,v) for k,v in environs.items()]

        print("{:-^20}".format(name))
        dump_to_stdout(service)

    return dc_deploy


def create_deploy(outdir: Path):

    prod = load_docker_compose()
    tools = load_docker_compose(".tools")

    merged = merge_docker_compose(prod, tools)

    dc_deploy = resolve_deploy(merged, exclude=["webclient"])
    fpath = outdir / "docker-compose.yml"
    dump_to_file(dc_deploy, fpath)

    # dc_devel = merge(dc_deploy, docker_compose(".devel"))
    # fpath = here() / "out" / "docker-compose.devel.yml"
    # yaml_dump(fpath, dc_deploy)





if __name__ == "__main__":
    create_deploy(output_dir())
