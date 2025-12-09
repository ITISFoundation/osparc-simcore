# Units

GB = 1024**3

# Formatting
HEADER_STR = "{:-^50}"

# Docker placement labels for node-specific constraints
# These keys are used to identify custom placement labels that can be applied to docker nodes
# and are stripped when nodes become empty for reuse
CUSTOM_PLACEMENT_LABEL_KEYS: tuple[str, ...] = (
    "product_name",
    "user_id",
    "project_id",
    "node_id",
    "group_id",
    "wallet_id",
)
