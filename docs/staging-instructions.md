# Management of creating staging release

The process of moving code from [Master](https://github.com/ITISFoundation/osparc-simcore/tree/master) branch to [Staging](https://github.com/ITISFoundation/osparc-simcore/tree/staging) branch is described here.

## Process

1. Create a PR from master to staging

```bash
export SPRINT_NAME=TheNameOfTheSprint
export GIT_SHA=TheGitSHAOfTheLatestSprintCommit
# clone the repo
git clone git@github.com:ITISFoundation/osparc-simcore.git
# create a branch from master at defined git SHA
git checkout -b FREEZE_${SPRINT_NAME} ${GIT_SHA}
# push the branch to git origin repo
git push --set-upstream origin FREEZE_${SPRINT_NAME}
# open the PR on github website
open https://github.com/ITISFoundation/osparc-simcore/compare/staging...FREEZE_${SPRINT_NAME}?expand=1&title=FREEZE_${SPRINT_NAME}
# create the log entries to be copied into the pull request
git log --oneline staging..HEAD --no-decorate
```

2. Once the PR is "green", do a **merge pull request** (NOTE: DO NOT SQUASH!!!)
3. The CI will be automatically triggered and will build/test/deploy
