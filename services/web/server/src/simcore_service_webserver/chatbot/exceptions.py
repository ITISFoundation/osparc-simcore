from common_library.errors_classes import OsparcErrorMixin


class BaseChatbotException(OsparcErrorMixin, Exception):
    """Base exception for chatbot errors"""


class NoResponseFromChatbotError(BaseChatbotException):
    msg_template = "No response received from chatbot for chat completion {chat_completion_id}"
