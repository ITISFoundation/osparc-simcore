# Notes on python's released packages


Keeps a list notes with relevant information about releases of python package. Some of the questions these notes might solve :

- Can you recommend me a package to do X?
- Is there a package / version of a package that I should NOT use? Which alternatives do I have?
- Is this package already (or will be) included in the current python standard library? If the latter, is there a backport package I can use right now?
- ...

## Packages Notes


- [importlib-metadata](https://importlib-metadata.readthedocs.io/en/latest/)
  - became part of the python standard library as [importlib.resources](https://docs.python.org/3/library/importlib.metadata.html) from python 3.8
- [importlib-resources](https://importlib-resources.readthedocs.io/en/latest/)
  - is a backport of Python 3.9’s standard library [importlib.resources](https://docs.python.org/3.7/library/importlib.html#module-importlib.resources)
- [packaging](https://packaging.pypa.io/en/latest/)
  - used for  version handling, specifiers, markers, requirements, tags, utilities. It follows several PEPs and will probably end up in the python standard library
- [dataclasses](https://pypi.org/project/dataclasses/)
  - a backport of the [``dataclasses`` module](https://docs.python.org/3/library/dataclasses.html) for Python 3.6. Included as dataclasses in standard library from python >=3.7.
  - here is included as a dependency to [pydantic](https://pydantic-docs.helpmanual.io/)
- [mock](https://pypi.org/project/mock/)
  - is a rolling backport of the standard library mock code available as unittest.mock in Python 3.3 onwards.



## Improvements

- An automatic way to "prune" a requirements list in a package: it is very common forgeting removing dependencies from the ``requirements.txt`` that we are not using anymore ... or as a result of a classic *copy&paste* snippet from another listing.
- Create a ``blocklist/passlist`` of requirements. Add a comment that justify every selection
- Integrate better dependenabot:
  - currently it only covers two packages of this repository
  - due to the hybrid nature of this repo, we cannot take full advantage of this great tool
- Several backports above show some of the dependencies that will dissapear with a python upgrade!
- TODO: compare pip-compile output vs freeze to check whether some dependencies are NOT pinned!
