from common_library.user_messages import user_message


def test_user_message() -> None:

    assert user_message("This is a user message") == "This is a user message"
