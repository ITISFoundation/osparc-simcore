# Notes on python's released packages

Keeps a list of notes with relevant information about releases of python packages. Some of the questions these notes might solve:

- Can you recommend me a package to do X?
- Is there a package / version of a package that I should NOT use? Which alternatives do I have?

## Packages Notes

- [packaging](https://packaging.pypa.io/en/latest/)
  - Used for version handling, specifiers, markers, requirements, tags, utilities. Follows several PEPs.

## Improvements

- **Auto-prune workflow**: Automatically remove unused dependencies from package requirements. Useful for:
  - Test dependencies: common to add/remove test packages frequently
  - Production: reduces installation size by eliminating unused dependencies
