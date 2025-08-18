from models_library.conversations import ConversationID, ConversationType
from pydantic import BaseModel, ConfigDict

from ..errors import ConversationUnsupportedTypeError


def raise_unsupported_type(conversation_type: ConversationType) -> None:
    raise ConversationUnsupportedTypeError(conversation_type=conversation_type)


class ConversationPathParams(BaseModel):
    conversation_id: ConversationID
    model_config = ConfigDict(extra="forbid")
