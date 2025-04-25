from ..errors import WebServerBaseError


class ConbersationError(WebServerBaseError, ValueError): ...


class ConversationErrorNotFoundError(ConbersationError):
    msg_template = "Conversation {conversation_id} not found"


class ConversationMessageErrorNotFoundError(ConbersationError):
    msg_template = "Conversation {conversation_id} message {message_id} not found"
