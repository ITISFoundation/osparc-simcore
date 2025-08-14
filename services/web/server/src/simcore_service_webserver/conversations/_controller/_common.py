from models_library.conversations import ConversationType

from ..errors import ConversationUnsupportedTypeError


def raise_unsupported_type(conversation_type: ConversationType) -> None:
    raise ConversationUnsupportedTypeError(conversation_type=conversation_type)
