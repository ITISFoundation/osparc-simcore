#!/bin/bash

# Check for the presence of @pytest.mark.testit in staged files
git diff --cached --name-only | while IFS= read -r file; do
    if grep -n '@pytest\.mark\.testit' "$file"; then
        sed -i '/@pytest\.mark\.testit/d' "$file"
        echo "Removed @pytest.mark.testit from file '$file'"
        exit 1
    fi
done
