# How to avoid pushing to upstream

To avoid accidents, consider removing push permissions on your upstream from
your local repository.

Go to  `\path-to\osparc-simcore-fork` and you should have a clean repo
```bash
git status
```
```
On branch master
Your branch is up-to-date with 'origin/master'.
nothing to commit, working directory clean
```

List remotes
```bash
git remote -vv
```
```
origin  git@github.com:USER/osparc-simcore.git (fetch)
origin  git@github.com:USER/osparc-simcore.git (push)
```


Setup upstream
```bash
git remote add upstream git@github.com:ITISFoundation/osparc-simcore.git
```

Overwrite push to disallow access
```bash
git remote set-url upstream --push "You_shall_not_push_but_use_PR_instead"
```

Final result will look similar to the following

```bash
git remote -vv
```
```
origin	git@github.com:USER/osparc-simcore-forked.git (fetch)
origin	git@github.com:USER/osparc-simcore-forked.git (push)
upstream	git@github.com:ITISFoundation/osparc-simcore.git (fetch)
upstream	You_shall_not_push_but_use_PR_instead (push)
```
