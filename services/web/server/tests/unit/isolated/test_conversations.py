from models_library.conversations import ConversationMessageType, ConversationType
from simcore_postgres_database.models.conversation_messages import (
    ConversationMessageType as PostgresConversationMessageType,
)
from simcore_postgres_database.models.conversations import (
    ConversationType as PostgresConversationType,
)


async def _test_conversation_enums():
    assert [member.value for member in ConversationType] == [
        member.value for member in PostgresConversationType
    ]
    assert [member.value for member in ConversationMessageType] == [
        member.value for member in PostgresConversationMessageType
    ]
