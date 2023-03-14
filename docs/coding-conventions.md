# Coding Conventions and Linters

Coding styles and linters are provided for the Javascript and Python.

## Javascript

In general the `qooxdoo` naming convention/style is followed. The [Access](http://qooxdoo.org/docs/#/core/oo_feature_summary?id=access) paragraph is the most notable. It is recommended to read the entire document.

Have a look at `ESLint`'s configuration files [.eslintrc.json](.eslintrc.json) and [.eslintignore](.eslintignore).

## Python

In short we use the following naming convention ( roughly  [PEP8](https://peps.python.org/pep-0008/) ):

|          | example                                       |
| -------- | --------------------------------------------- |
| Function | `function`, `my_fun­ction`                    |
| Variable | `x`, `var`, `my_variable`                     |
| Class    | `Model`, `MyClass`                            |
| Method   | `class_`­`method`, `method`                   |
| Constant | `CONSTANT`, `MY_CONSTANT`, `MY_LONG_CONSTANT` |
| Module   | `module.py`, `my_module.py`                   |
| Package  | `package`, `my_package`                       |

- We encourage marking protected/private entities. We do it adding the prefix `_`/`__`: e.g. `_PROTECTED_CONSTANT`, `A.__private_func`
- We encourage **meaningful** type annotations

For the rest basically:
- [black] will enforce the style: Just use it.
- [pylint] will check the some extra conventions: see [.pylintrc](../.pylintrc).
- [mypy] will check syntax : see [mypy.ini](../mypy.ini)

[mypy]:https://www.mypy-lang.org/
[black]:https://black.readthedocs.io/en/stable/index.html
[pylint]:https://pylint.readthedocs.io/en/latest/


## Postgres

### Foreign keys

- Name pattern: ```fk_$(this_table)_$(this_column)```, for example ```fk_projects_to_product_product_name```


## Shell Scripts

- Recommended style: https://google.github.io/styleguide/shellguide.html
- Automatic analysis tool: [shellcheck](https://www.shellcheck.net)
  - see ``scripts/shellcheck.bash`` and ``.vscode/settings.template.json``


## General

<!-- Add below this line coding agreed coding conventions and give them a number !-->

###  CC1: Can I use ``TODO:``, ``FIXME:``?

We should avoid merging PRs with ``TODO:`` and ``FIXME:`` into master. One of our bots detects those and flag them as code-smells. If we still want to keep this idea/fix noted in the code, those can be rewritten as ``NOTE:`` and should be extended with a link to a github issue with more details. For a context, see [discussion here](https://github.com/ITISFoundation/osparc-simcore/pull/3380#discussion_r979893502).


## Retries

[Tenacity](https://github.com/jd/tenacity) wherever a retry is required. While most retries are straight forward consider [the following article](https://aws.amazon.com/blogs/architecture/exponential-backoff-and-jitter/) regarding retries services and how to avoid overwhelming them.

When retrying an API call (or some sort of request) to an external system, consider that that system can have trouble replying.
It is most effective to create a retry using `wait_random_exponential` from tenacity which implements what the article above describes.
