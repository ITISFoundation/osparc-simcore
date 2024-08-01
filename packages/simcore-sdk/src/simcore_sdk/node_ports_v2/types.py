import re

from models_library.basic_regex import PROPERTY_KEY_RE
from pydantic import ConstrainedStr


class PortKey(ConstrainedStr):
    regex = re.compile(PROPERTY_KEY_RE)
