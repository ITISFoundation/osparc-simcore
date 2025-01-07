from common_library.errors_classes import OsparcErrorMixin


class ArchiveError(OsparcErrorMixin, Exception):
    """base error class"""


class CouldNotFindValueError(ArchiveError):
    msg_template = "Unexpected value for '{field_name}'. Should not be None"


class CouldNotRunCommandError(ArchiveError):
    msg_template = "Command '{command}' failed with error:\n{command_output}"


class TableHeaderNotFoundError(ArchiveError):
    msg_template = (
        "Excepted to detect a table header since files were detected "
        "file_lines='{file_lines}'. "
        "Command output:\n{command_output}"
    )
