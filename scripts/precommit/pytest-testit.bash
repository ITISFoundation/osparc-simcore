#!/bin/bash

git diff --cached --name-only | while IFS= read -r file; do
    if grep -n '@pytest\.mark\.testit' "$file"; then
        sed -i '/@pytest\.mark\.testit/d' "$file"
        exit 1
    fi
done
