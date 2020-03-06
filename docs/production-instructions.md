# Deployment of production environment


The production environment is automaticaly built and deployed upon creation of a new  [release](https://github.com/ITISFoundation/osparc-simcore/releases/).


- A new release adds a tag to [staging branch](https://github.com/ITISFoundation/osparc-simcore/branches) as ``v1.2.3``.
- Release notes shall be human readable and shall summarize briefly the commits in staging since last release, i.e.
```
git log --pretty=oneline --abbrev-commit v1.1.55..HEAD
```
where ``v1.1.55` is supposed to be the last release.


## Magic behind the scene

TODO: deployment workflow: who and when is involved in deploying production
