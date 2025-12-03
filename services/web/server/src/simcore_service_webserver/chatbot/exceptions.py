class BaseChatbotException(Exception):
    """Base exception for chatbot errors"""


class InvalidUserMessageError(BaseChatbotException):
    """Raised when the user message is invalid"""


class NoResponseFromChatbotError(BaseChatbotException):
    """Raised when no response is received from the chatbot"""
