""" Path points in the source's tree

Notice that this tree structure will change upon instalation!

"""
import sys
import pathlib

_CURRENT_FOLDER = pathlib.Path( sys.argv[0] if __name__ == "__main__" else __file__).parent

# TODO: check if installed?

ROOT_FOLDER = _CURRENT_FOLDER.parent.parent.parent
SOURCE_FOLDER = ROOT_FOLDER / "src"
CONFIG_FOLDER = ROOT_FOLDER / "config"
