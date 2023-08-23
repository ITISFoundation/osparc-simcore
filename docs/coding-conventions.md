# Coding Conventions, Linters and Definitions

Some conventions on coding style and tools for the Javascript and Python in this repository.

----

## Definitions

What is a ...

- **Controller-Service-Repository** design-pattern ?
  - An introduction: https://tom-collings.medium.com/controller-service-repository-16e29a4684e5
  - Example of adopted convention: https://github.com/ITISFoundation/osparc-simcore/pull/4389



----
## General Coding Conventions

<!-- Add below this line coding agreed coding conventions and give them a number !-->

###  CC1: Can I use ``TODO:``, ``FIXME:``?

We should avoid merging PRs with ``TODO:`` and ``FIXME:`` into master. One of our bots detects those and flag them as code-smells. If we still want to keep this idea/fix noted in the code, those can be rewritten as ``NOTE:`` and should be extended with a link to a github issue with more details. For a context, see [discussion here](https://github.com/ITISFoundation/osparc-simcore/pull/3380#discussion_r979893502).


### CC2: No commented code

Avoid commented code, but if you *really* want to keep it then add an explanatory `NOTE:`
```python
import os
# import bar
# x = "not very useful"

# NOTE: I need to keep this becase ...
# import foo
# x = "ok"
```

### CC3 ...

----
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
- We encourage [pep257] for **simple** code documentation
  - Priorize having good variable names and type annotations than a verbose and redundant documentation
  - Examples of useful documentation:
    - Raised *Exceptions* in a function
    - *Rationale* of a design
    - *Extra information* on variable/argument that cannot be deduced from its name or type annotation
  - Use vscode tool `njpwerner.autodocstring`
  - See [example](https://github.com/NilsJPWerner/autoDocstring/blob/HEAD/docs/pep257.md) of [pep257] doc.

### For the rest ... (tools)

- [black] will enforce the style: Just use it.
- [pylint] will check the some extra conventions: see [.pylintrc](../.pylintrc).
  - ``make pylint`` recipe available on ``packages`` or ``services``
- [mypy] is a type-checker that will check syntax : see [mypy.ini](../mypy.ini)
  - See intro in [mypy-doc]
  - ``make mypy`` recipe available on ``packages`` or ``services``


----

## Postgres

- **Foreign Keys** follow this name pattern: ```fk_$(this_table)_$(this_column)```, for example ```fk_projects_to_product_product_name```


----
## Shell Scripts

- Recommended style: https://google.github.io/styleguide/shellguide.html
- Automatic analysis tool: [shellcheck](https://www.shellcheck.net)
  - see ``scripts/shellcheck.bash`` and ``.vscode/settings.template.json``
- Recommended inside of a ``scripts`` folder




----
## Javascript

In general the `qooxdoo` naming convention/style is followed. The [Access](http://qooxdoo.org/docs/#/core/oo_feature_summary?id=access) paragraph is the most notable. It is recommended to read the entire document.

Have a look at `ESLint`'s configuration files [.eslintrc.json](.eslintrc.json) and [.eslintignore](.eslintignore).



<!-- Keep the space below here for a SORTED list of references -->

[black]:https://black.readthedocs.io/en/stable/index.html
[mypy-doc]:https://mypy.readthedocs.io/en/latest/
[mypy]:https://www.mypy-lang.org/
[pep257]:https://peps.python.org/pep-0257/
[pylint]:https://pylint.readthedocs.io/en/latest/
