def user_message(msg: str, *, _version: int | None = None) -> str:
    """Marks a message as user-facing.

    Implements the *prose-as-key* pattern: the English prose itself is the
    gettext msgid, so no separate key registry is needed.  The string returned
    by this function is the canonical msgid used by the i18n pipeline
    (``common_library.i18n``).  Extraction tools scan call
    sites of ``user_message`` to build the gettext catalog; at runtime callers
    pass the returned msgid to ``get_translator(locale).gettext(msgid)`` to
    obtain the localised string.

    Arguments:
        msg -- human-friendly string that follows docs/user-messages-guidelines.md
        _version -- version number to track changes to messages; increment when modifying an existing message

    Returns:
        The original message string, allowing it to be used inline in code
    """
    return msg
