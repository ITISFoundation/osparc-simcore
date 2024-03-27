#!/bin/bash

# Get a list of all staged files
staged_files=$(git diff --cached --name-only --diff-filter=ACM)

# Loop through each file
for file in $staged_files
do
  # Check if the file name contains "docker-compose" and is a .yml or .yaml file
  if [[ $file == *docker-compose*.yml || $file == *docker-compose*.yaml ]]; then
    echo "Checking $file" 1>&2
    # Check the file for lines with more than one dollar sign
    if grep -n -P '\$\{[^}]*\$\{[^}]*\}[^}]*\}' "$file"; then
      echo "Error: $file contains a line with more than one dollar sign."
      exit 1
    elif grep -n -P '\$[a-zA-Z_][a-zA-Z0-9_]*' "$file"; then
      echo "Error: $file contains a line with an environment variable not wrapped in curly braces."
      exit 1
    fi
  fi
done


# If no errors were found, allow the commit
exit 0
