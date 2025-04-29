from ..errors import WebServerBaseError


class ConversationError(WebServerBaseError, ValueError): ...


class ConversationErrorNotFoundError(ConversationError):
    msg_template = "Conversation {conversation_id} not found"


class ConversationMessageErrorNotFoundError(ConversationError):
    msg_template = "Conversation {conversation_id} message {message_id} not found"
