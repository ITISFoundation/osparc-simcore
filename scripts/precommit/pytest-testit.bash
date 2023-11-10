#!/bin/bash

# Check for the presence of @pytest.mark.testit in staged files
git diff --cached --name-only | while IFS= read -r file; do
    if grep -q '@pytest\.mark\.testit' "$file"; then
        echo "Error: Your commit contains '@pytest.mark.testit' in file '$file'. Please remove it before committing."
        exit 1
    fi
done
