# NOTE: this is a duplicate, but currently we don't want to enforce a dependency between
# service-library and models-library
# should go away and removed when the following case is solved
# https://github.com/ITISFoundation/osparc-simcore/issues/4013

from enum import Enum, unique


@unique
class StrAutoEnum(str, Enum):
    @staticmethod
    def _generate_next_value_(name, start, count, last_values):
        return name.upper()
