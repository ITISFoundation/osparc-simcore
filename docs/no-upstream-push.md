# How to avoid pushing to upstream

To avoid accidents, consider removing push permissions on your upstream from
your local repository.


    \path-to\osparc-simcore (master -> origin)
    $ git status
    On branch master
    Your branch is up-to-date with 'origin/master'.
    nothing to commit, working directory clean

    \path-to\osparc-simcore (master -> origin)
    $ git remote -vv
    origin  git@github.com:ITISFoundation/osparc-simcore.git (fetch)
    origin  git@github.com:ITISFoundation/osparc-simcore.git (push)

    \path-to\osparc-simcore (master -> origin)
    $ git remote add upstream git@github.com:GITUSER/osparc-simcore.git

    \path-to\osparc-simcore (master -> origin)
    $ git remote set-url upstream --push "You shall not push but use PR instead"

    \path-to\osparc-simcore (master -> origin)
    $ git remote -vv
    origin  git@github.com:ITISFoundation/osparc-simcore.git (fetch)
    origin  git@github.com:ITISFoundation/osparc-simcore.git (push)
    upstream        git@github.com:GITUSER/osparc-simcore.git (fetch)
    upstream        You shall not push but use PR instead (push)
