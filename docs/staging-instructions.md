# Management of creating staging release

The process of creating a staging release version of code from [Master](https://github.com/ITISFoundation/osparc-simcore/tree/master) is described here.

## Description

A staging release is a specific tagged version of one commit in the Master branch

## Process

1. Create a tag on a specific commit of master

    ```bash
    export SPRINT_NAME=TheNameOfTheSprint
    export GIT_SHA=TheGitSHAOfTheLatestSprintCommit
    export SPRINT_VERSION=1
    # clone the repo
    git clone git@github.com:ITISFoundation/osparc-simcore.git
    # get the latest tag
    latest_tag=$(git describe --tags --abbrev=0)
    # create the log entries to be copied into the release body
    body=$(scripts/url-encoder.bash "$(git log ${latest_tag}..${GIT_SHA} --pretty="format:- %s")")
    # tag the commit
    echo "https://github.com/sanderegg/osparc-simcore/releases/new?prerelease=1&target=${GIT_SHA}&tag=FREEZE_${SPRINT_NAME}${SPRINT_VERSION}&title=Staging%20${SPRINT_NAME}${SPRINT_VERSION}&body=$body"
    ```

2. Adjust the list of changes if needed
3. Press the **Publish release** button
4. The CI will be automatically triggered and will deploy the staging release
