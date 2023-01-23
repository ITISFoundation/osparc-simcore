from enum import Enum, unique


@unique
class StrAutoEnum(str, Enum):
    @staticmethod
    def _generate_next_value_(name, start, count, last_values):
        return name.upper()
