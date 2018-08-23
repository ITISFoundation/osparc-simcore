import sys
import warnings
import logging

warnings.filterwarnings("ignore")

from . import cli
from . import settings
from .main import run

def main(argv=None):
    logging.basicConfig(level=logging.DEBUG)

    if argv is None:
        argv = sys.argv[1:]

    ap = cli.add_options()
    options = cli.parse_options(argv, ap)
    config = settings.config_from_options(options)

    run(config)

if __name__ == "__main__":
    main(sys.argv[1:])
