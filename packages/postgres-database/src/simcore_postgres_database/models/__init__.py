""" tables

  We use a classical Mapping w/o using a Declarative system.

 See https://docs.sqlalchemy.org/en/latest/orm/mapping_styles.html#classical-mappings
 """
import glob
from os.path import basename, dirname, isfile, join

modules = glob.glob(join(dirname(__file__), "*.py"))

__all__ = [
    basename(f)[:-3] for f in modules if isfile(f) and not f.endswith("__init__.py")
]
