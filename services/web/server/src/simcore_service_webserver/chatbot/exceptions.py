from common_library.errors_classes import OsparcErrorMixin


class BaseChatbotException(OsparcErrorMixin, Exception):
    """Base exception for chatbot errors"""


class InvalidUserInConversationError(BaseChatbotException):
    msg_template = "Encountered unexpected user {primary_group_id} in conversation {conversation_id}"


class NoResponseFromChatbotError(BaseChatbotException):
    msg_template = (
        "No response received from chatbot for chat completion {chat_completion_id}"
    )
