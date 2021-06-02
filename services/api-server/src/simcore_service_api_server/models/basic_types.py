from models_library.basic_regex import VERSION_RE
from pydantic import constr

VersionStr = constr(strip_whitespace=True, regex=VERSION_RE)  # as M.m.p
