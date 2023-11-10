#!/bin/bash

# Remove the line containing @pytest.mark.testit in staged files
git diff --cached --name-only | grep -E '\.x$' | while IFS= read -r file; do
    sed -i '/@pytest\.mark\.testit/d' "$file"
    git add "$file"
    echo "Removed @pytest.mark.testit from $file"
    exit 1
done
