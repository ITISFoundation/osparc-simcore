#
# NOTE: https://github.com/ITISFoundation/osparc-simcore/issues/3486
#

PROPERTY_TYPE_RE = r"^(number|integer|boolean|string|ref_contentSchema|data:([^/\s,]+/[^/\s,]+|\[[^/\s,]+/[^/\s,]+(,[^/\s]+/[^/,\s]+)*\]))$"
PROPERTY_TYPE_TO_PYTHON_TYPE_MAP = {
    "integer": int,
    "number": float,
    "boolean": bool,
    "string": str,
}

FILENAME_RE = r".+"
