import sys
import warnings
import logging

# TODO: refactor as in cookiecutter
warnings.filterwarnings("ignore")

from . import cli
from . import settings
from .application import run_service

def main(argv=None):
    #logging.basicConfig(level=logging.DEBUG)

    if argv is None:
        argv = sys.argv[1:]

    ap = cli.add_options()
    options = cli.parse_options(argv, ap)
    config = settings.config_from_options(options)

    log_level = config.get("app",{}).get("log_level", "DEBUG")
    logging.basicConfig( level=getattr(logging, log_level) )

    run_service(config)

if __name__ == "__main__":
    main(sys.argv[1:])
