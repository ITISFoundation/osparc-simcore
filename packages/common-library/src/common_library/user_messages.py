def user_message(msg: str, *, _version: int | None = None) -> str:
    """Marks a message as user-facing

    Arguments:
        msg -- human-friendly string that follows docs/user-messages-guidelines.md
        _version -- version number to track changes to messages; increment when modifying an existing message

    Returns:
        The original message string, allowing it to be used inline in code
    """
    return msg
