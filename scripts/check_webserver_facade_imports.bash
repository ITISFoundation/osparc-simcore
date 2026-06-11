#!/bin/bash
#
# Check that web-server cross-domain imports respect the public facade pattern.
#
# Ensures that imports from other domains use only:
#   from ..<<domain>>.<<domain>>_service import ...
#
# And prohibits:
#   from ..<<domain>>._<<private>> import ...
#   from ..<<domain>>.models import ...
#   from ..<<domain>>.exceptions import ...
#   from ..<<domain>>.api import ...
#   from ..<<domain>>.service import ...
#
# NOTE: projects domain refactoring is Phase 2 (not yet complete)
#

set -e

WEBSERVER_SRC="services/web/server/src/simcore_service_webserver"
REFACTORED_DOMAINS=("groups" "wallets" "folders" "workspaces" "products" "users")
PENDING_DOMAINS=("projects")  # Phase 2: Not yet refactored
VIOLATIONS=0

echo "Checking web-server facade import boundaries..."
echo ""

# Check for imports that bypass facades (REFACTORED DOMAINS ONLY)
for domain in "${REFACTORED_DOMAINS[@]}"; do
    # Pattern 1: from ..<<domain>>._ (private modules)
    # But exclude imports within the domain itself (from ._)
    echo "Checking for private module imports from $domain..."

    if grep -r "from \.\.$domain\._" "$WEBSERVER_SRC" \
        --include="*.py" \
        --exclude-dir="__pycache__" \
        | grep -v "^$WEBSERVER_SRC/$domain/" ; then
        echo "ERROR: Found imports bypassing $domain facade (using private modules)"
        VIOLATIONS=$((VIOLATIONS + 1))
    fi
done

# Check for reach-through imports of models and exceptions (DESIGN.md rule)
echo "Checking for models/exceptions reach-through imports..."

for domain in "${REFACTORED_DOMAINS[@]}"; do
    # Pattern: from ..<<domain>>.models or exceptions (reach-through)
    if grep -r "from \.\.$domain\.\(models\|exceptions\) import" "$WEBSERVER_SRC" \
        --include="*.py" \
        --exclude-dir="__pycache__" \
        | grep -v "^$WEBSERVER_SRC/$domain/"; then
        echo "ERROR: Found reach-through imports from $domain (models/exceptions must go through facade)"
        VIOLATIONS=$((VIOLATIONS + 1))
    fi
done

# Special checks for old naming conventions (REFACTORED DOMAINS ONLY)
echo "Checking for old naming conventions..."

# Check for old .api imports
if grep -r "from \.\.groups\.api import" "$WEBSERVER_SRC" --include="*.py" --exclude-dir="__pycache__"; then
    echo "ERROR: Found old groups.api imports (should use groups.groups_service)"
    VIOLATIONS=$((VIOLATIONS + 1))
fi

if grep -r "from \.\.wallets\.api import" "$WEBSERVER_SRC" --include="*.py" --exclude-dir="__pycache__"; then
    echo "ERROR: Found old wallets.api imports (should use wallets.wallets_service)"
    VIOLATIONS=$((VIOLATIONS + 1))
fi

if grep -r "from \.\.workspaces\.api import" "$WEBSERVER_SRC" --include="*.py" --exclude-dir="__pycache__"; then
    echo "ERROR: Found old workspaces.api imports (should use workspaces.workspaces_service)"
    VIOLATIONS=$((VIOLATIONS + 1))
fi

if grep -r "from \.\.folders\.service import" "$WEBSERVER_SRC" --include="*.py" --exclude-dir="__pycache__"; then
    echo "ERROR: Found old folders.service imports (should use folders.folders_service)"
    VIOLATIONS=$((VIOLATIONS + 1))
fi

echo ""
echo "Note: Phase 2 (projects domain refactoring) is pending. Projects still uses:"
echo "  - from ..projects.api (should become projects.projects_service)"
echo "  - from ..projects.models (should go through projects facade)"
echo ""

if [ $VIOLATIONS -eq 0 ]; then
    echo "✓ All Phase 1 facade imports are correct (groups, wallets, folders, workspaces, products, users)"
    exit 0
else
    echo "✗ Found $VIOLATIONS violation(s) in Phase 1 domains"
    exit 1
fi
