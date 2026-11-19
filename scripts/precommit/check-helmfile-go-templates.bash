#!/bin/bash

exit_code=0

report() {
    local message="$1" pattern="$2" file="$3"
    local matches
    matches=$(grep -nE "$pattern" "$file" | grep -vE '^[0-9]+:[[:space:]]*#')
    if [ -n "$matches" ]; then
        echo "$message" 1>&2
        echo "$matches" 1>&2
        exit_code=1
    fi
}

# Three patterns &[A-Za-z_], *[A-Za-z_], and <<:
# that follow after whitespace or the beginning of a line.
anchors='(^|[[:space:]])(&[A-Za-z_]|\*[A-Za-z_]|<<:)'

for file in "$@"; do
    report "$file: use Go template variables instead of YAML anchors, aliases and merge keys" "$anchors" "$file"
done

exit $exit_code
