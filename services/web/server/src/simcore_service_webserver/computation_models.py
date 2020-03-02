""" API to ORM data conversions

"""
import re

from simcore_postgres_database.models.comp_tasks import NodeClass

# TODO: has to sync with /api/v0/schemas/project-v0.0.1.json
# TODO:  test agains all names in registry/fake projects??
node_key_re = re.compile(r"^simcore/services/(comp|dynamic|frontend)(/[^\s/]+)+$")
str_to_nodeclass = {
    'comp': NodeClass.COMPUTATIONAL,
    'dynamic': NodeClass.INTERACTIVE,
    'frontend': NodeClass.FRONTEND,
}

def to_node_class(node_key: str) -> NodeClass:
    match = node_key_re.match(node_key)
    if match:
        return str_to_nodeclass.get(match.group(1))
    return None

