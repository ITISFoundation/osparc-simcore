# TODO: redo with cookie-cutter
import sys

from .utils import output_dir
from .swarm_composer import create_deploy

def main(args=None):
    if args is None:
        args = sys.argv[1:]

    # TODO: use click to create cli!
    outdir = output_dir()
    create_deploy(outdir)
