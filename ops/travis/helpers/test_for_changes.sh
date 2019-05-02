#!/bin/bash
# http://redsymbol.net/articles/unofficial-bash-strict-mode/
set -euo pipefail
IFS=$'\n\t'

# Usage:
# test_for_changes ^web/server webserver blah
# this will test if these regexp are part of the modified files since the branching,
# or on the push commit range if running on travis

# detect travis
if [ ! -v TRAVIS ] || [ $TRAVIS = "false" ]; then
    CHANGES=$(git --no-pager diff --name-only FETCH_HEAD $(git merge-base FETCH_HEAD master))
else
    if [  "$TRAVIS_PULL_REQUEST" = "false"  ] && [ "$TRAVIS_BRANCH" = "master" ]; then
        echo "master branch detected, it's the same as if changes were done"
        exit 0
    fi
    CHANGES=$(git --no-pager diff --name-only $TRAVIS_COMMIT_RANGE)
fi

# look for changes
for i in .travis.yml ops/travis/.+-testing/ ops/travis/helpers/ "$@"; do
    # echo "checking if last changes contain $i regexp..."
    if egrep -q -- "$i" <<< $CHANGES; then
        echo "changes detected!"
        exit 0
    fi
done

exit 1
