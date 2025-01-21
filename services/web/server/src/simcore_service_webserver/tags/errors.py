from ..errors import WebServerBaseError


class TagsPermissionError(WebServerBaseError, PermissionError):
    ...


class ShareTagWithEveryoneNotAllowedError(TagsPermissionError):
    msg_template = (
        "User {user_id} is not allowed to share (or unshare) tag {tag_id} with everyone"
    )


class ShareTagWithProductGroupNotAllowedError(TagsPermissionError):
    msg_template = (
        "User {user_id} is not allowed to share  (or unshare) tag {tag_id} with group {group_id}. "
        "Only {user_role}>=TESTER users are allowed."
    )


class InsufficientTagShareAccessError(TagsPermissionError):
    msg_template = (
        "User {user_id} does not have sufficient access rights to share"
        " (or unshare) or unshare tag {tag_id}."
    )
