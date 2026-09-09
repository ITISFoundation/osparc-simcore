from typing import Annotated

from annotated_types import doc


def user_message(
    msg: Annotated[str, doc("Human-friendly string following docs/user-messages-guidelines.md")],
    *,
    _version: Annotated[
        int | None,
        doc("Increment when modifying an existing message to track changes in the catalog"),
    ] = None,
    _hint: Annotated[
        str | None,
        doc(
            "Translator note (e.g. length constraints, UI context). "
            "Emitted as a ``#. @TRANSLATOR`` line in the .pot by the extractor. "
            "Must be a plain string literal — f-strings are not supported."
        ),
    ] = None,
) -> Annotated[str, doc("The original message string, usable inline at the call site")]:
    """Marks a message as user-facing.

    Implements the *prose-as-key* pattern: the English prose itself is the
    gettext msgid, so no separate key registry is needed.  The string returned
    by this function is the canonical msgid used by the i18n pipeline
    (``common_library.gettext_support``).  Extraction tools scan call
    sites of ``user_message`` to build the gettext catalog; at runtime callers
    pass the returned msgid to ``get_translator(locale).gettext(msgid)`` to
    obtain the localised string.
    """
    return msg
