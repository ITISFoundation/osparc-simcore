#!/bin/bash

# Check for the presence of @pytest.mark.testit in staged files
if git diff --cached --name-only | grep -E '\.x$' | xargs grep -n '@pytest\.mark\.testit'; then
    echo "Error: Your commit contains '@pytest.mark.testit'. Please remove it before committing."
    exit 1
fi
