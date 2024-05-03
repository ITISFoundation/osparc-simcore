"""
A media type (also known as a Multipurpose Internet Mail Extensions or MIME type)
indicates the nature and format of a document, file, or assortment of bytes.

MIME types are defined and standardized in IETF's RFC 6838.


SEE https://developer.mozilla.org/en-US/docs/Web/HTTP/Basics_of_HTTP/MIME_types
"""
from typing import Final

# NOTE: mimetypes (https://docs.python.org/3/library/mimetypes.html) is already a module in python

MIMETYPE_APPLICATION_JSON: Final[str] = "application/json"
MIMETYPE_APPLICATION_ND_JSON: Final[str] = "application/x-ndjson"
MIMETYPE_APPLICATION_ZIP: Final[str] = "application/zip"
MIMETYPE_TEXT_HTML: Final[str] = "text/html"
MIMETYPE_TEXT_PLAIN: Final[str] = "text/plain"
