# Agent instructions

## Instructions

Detailed rules live in `.github/instructions/`, matched to files by `applyTo`
globs. Read the one that matches what you are editing:

- [General repository conventions](.github/instructions/general.instructions.md)
- [Python instructions](.github/instructions/python.instructions.md)
- [Python test instructions](.github/instructions/python-tests.instructions.md)
- [aiohttp instructions](.github/instructions/aiohttp.instructions.md)
- [Web-server instructions](.github/instructions/services-webserver.instructions.md)
- [Web-server OpenAPI spec stubs](.github/instructions/web-server-openapi.instructions.md)
- [Requirements file conventions](.github/instructions/requirements.instructions.md)
- [Makefile authoring conventions](.github/instructions/makefiles.instructions.md)
- [GitHub workflow instructions](.github/instructions/github-workflows.instructions.md)
- [JavaScript](.github/instructions/node.instructions.md)

## graphify

For any question about this repo's architecture, structure, components, or how
to add/modify/find code, your first action should be
`graphify query "<question>"` when `graphify-out/graph.json` exists. Use
`graphify path "<A>" "<B>"` for relationship questions and
`graphify explain "<concept>"` for focused-concept questions. These return a
scoped subgraph, usually much smaller than the full report or raw grep output.

Triggers: "how do I...", "where is...", "what does ... do",
"add/modify a `<component>`", "explain the architecture", or anything that
depends on how files or classes relate.

If `graphify-out/wiki/index.md` exists, use it for broad navigation. Read
`graphify-out/GRAPH_REPORT.md` only for broad architecture review or when
query/path/explain do not surface enough context. Only read source files when
(a) modifying/debugging specific code, (b) the graph lacks the needed detail,
or (c) the graph is missing or stale.

Type `/graphify` in Copilot Chat to build or update the graph.
