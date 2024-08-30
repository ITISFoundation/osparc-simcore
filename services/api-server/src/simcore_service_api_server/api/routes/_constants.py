from typing import Final

#
# CHANGELOG formatted-messages for API routes
#
# - Append at the bottom of the route's description
# - These are displayed in the swagger doc
# - These are displayed in client's doc as well (auto-generator)
# - Inspired on this idea https://www.sphinx-doc.org/en/master/usage/restructuredtext/directives.html#describing-changes-between-versions
#

# new routes
FMSG_CHANGELOG_NEW_IN_VERSION: Final[str] = "New in *version {}*\n"

# new inputs/outputs in routes
FMSG_CHANGELOG_ADDED_IN_VERSION: Final[str] = "Added in *version {}*: {}\n"

# changes on inputs/outputs in routes
FMSG_CHANGELOG_CHANGED_IN_VERSION: Final[str] = "Changed in *version {}*: {}\n"

# removed on inputs/outputs in routes
FMSG_CHANGELOG_REMOVED_IN_VERSION_FORMAT: Final[str] = "Removed in *version {}*: {}\n"
