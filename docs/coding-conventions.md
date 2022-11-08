# Coding Conventions and Linters

Coding styles and linters are provided for the Javascript and Python.

## Javascript

In general the `qooxdoo` naming convention/style is followed. The [Access](http://qooxdoo.org/docs/#/core/oo_feature_summary?id=access) paragraph is the most notable. It is recommended to read the entire document.

Have a look at `ESLint`'s configuration files [.eslintrc.json](.eslintrc.json) and [.eslintignore](.eslintignore).

## Python

`Black` will enforce the style. Just use it.

Have a look at `Pylint`'s configuration file [.pylintrc](.pylintrc).


## Posgres

### Foreign keys

- name pattern: ```fk_$(this_table)_$(this_column)```, for example ```fk_projects_to_product_product_name```


## Shell Scripts

- Recommended style: https://google.github.io/styleguide/shellguide.html
- Automatic analysis tool: [shellcheck](https://www.shellcheck.net)
  - see ``scripts/shellcheck.bash`` and ``.vscode/settings.template.json``


## General

<!-- Add below this line coding agreed coding conventions and give them a number !-->

###  CC1: Can I use ``TODO:``, ``FIXME:``?

We should avoid merging PRs with ``TODO:`` and ``FIXME:`` into master. One of our bots detects those and flag them as code-smells. If we still want to keep this idea/fix noted in the code, those can be rewritten as ``NOTE:`` and should be extended with a link to a github issue with more details. For a context, see [discussion here](https://github.com/ITISFoundation/osparc-simcore/pull/3380#discussion_r979893502).
