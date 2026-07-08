# i18n — Backend & Frontend Localization

Orchestrates extraction, merging, AI translation, and compilation of message catalogs for the osparc-simcore backend and frontend.

Output catalog: `packages/common-library/src/common_library/locale/`

---

## Terminology

**Internationalization (i18n):** Engineering the product to support multiple languages and locales without hardcoding locale-specific assumptions.
Example: the `user_message()` API, locale-aware request middleware, runtime catalog lookup via gettext.

**Localization (l10n):** Adapting the product for specific locales (translating strings, formatting dates/currency, switching layout direction, etc.).
Example: the extraction, translation, and compilation workflow orchestrated by this Makefile.

**Relationship:** i18n is prerequisite infrastructure (built once, per-service); l10n is the process this folder automates (repeated per target market).

---

## Quick Start

The two catalogs are **separately owned** and each has its own symmetric pipeline.
There is no combined `all` target — run the catalog you need:

```bash
# Run from repo root or any directory
make -C scripts/i18n backend-all     # backend-extract -> backend-translate -> backend-compile
make -C scripts/i18n frontend-all    # frontend-extract -> frontend-translate
```

## Backend catalog

`packages/common-library/src/common_library/locale/messages.{pot,po,mo}`

| Step | Target              | Description                                                                          |
| ---- | ------------------- | ------------------------------------------------------------------------------------ |
| 1    | `backend-extract`   | Extract `user_message()` (Python) + `{% trans %}` (Jinja) → `messages.pot` (+enrich) |
| —    | `backend-plan`      | Dry-run: log the LLM prompts that step 2 WOULD send (no call, no save)               |
| 2    | `backend-translate` | AI translate stale entries (one `.po` per `LANG`)                                    |
| 3    | `backend-compile`   | `msgfmt` backend `.po` → `.mo`                                                       |

```bash
make -C scripts/i18n backend-extract
make -C scripts/i18n backend-translate
make -C scripts/i18n backend-compile
```

## Frontend catalog

`services/static-webserver/client/source/translation/{frontend.pot,*.po}`
(no `.mo` — qooxdoo's `qx compile` reads `.po` directly)

| Step | Target               | Description                                                            |
| ---- | -------------------- | ---------------------------------------------------------------------- |
| 1    | `frontend-extract`   | Extract `this.tr()` strings → `frontend.pot` (+enrich)                 |
| —    | `frontend-plan`      | Dry-run: log the LLM prompts that step 2 WOULD send (no call, no save) |
| 2    | `frontend-translate` | `msgmerge` + AI translate entries (one `.po` per `CLIENT_LANGS`)       |

```bash
make -C scripts/i18n frontend-extract
make -C scripts/i18n frontend-translate
make -C scripts/i18n frontend-translate CLIENT_LANGS="de_DE"   # specific language
```

Frontend `.po` files are output to `services/static-webserver/client/source/translation/{lang}.po`.

## Dry-run (plan)

`backend-plan` / `frontend-plan` run the real translation pipeline but swap the LLM
client for a dry-run stand-in: each entry that WOULD be translated has its **composed
prompt printed and appended to the log file**, and a stub `(dry-run)` response is
returned instead of calling the model. No tokens are spent, no API key is needed, and
nothing is written to the `.po`. Use it to review which entries are stale and to
inspect the exact prompts (glossary, translator notes, source snippet) sent to the LLM.

```bash
make -C scripts/i18n backend-plan
make -C scripts/i18n frontend-plan
```

## Key Variables

| Variable       | Default         | Description                             |
| -------------- | --------------- | --------------------------------------- |
| `LANGS`        | `zh_CN es_ES`   | Backend locale codes to translate       |
| `CLIENT_LANGS` | `es_ES zh_CN`   | Frontend locale codes to translate      |
| `MODEL`        | `openai/gpt-4o` | LiteLLM model string                    |
| `BASE_URL`     | _(empty)_       | Custom LLM endpoint (e.g. local Ollama) |
| `PARALLEL`     | `false`         | Enable parallel translation workers     |
| `MAX_WORKERS`  | `4`             | Worker count when `PARALLEL=true`       |
| `USE_GIT`      | `true`          | Skip already-committed translations     |

## Model

The default model is `openai/gpt-4o`. Override inline via `MODEL` (and `BASE_URL` for
self-hosted OpenAI-compatible endpoints, e.g. local Ollama):

```bash
make -C scripts/i18n backend-translate MODEL=anthropic/claude-sonnet-4-6
make -C scripts/i18n backend-translate MODEL=ollama/llama3.1 BASE_URL=http://localhost:11434
```

## Override Language Inline

```bash
make -C scripts/i18n backend-translate LANGS="de_DE fr_FR"
```

## Per Service / Package

There is no dedicated per-service target. Override `I18N_DIRS` to scope extraction or validation to one service or package:

```bash
# Extract only one service
make -C scripts/i18n backend-extract I18N_DIRS=services/api-server

# Validate style for one package
make -C scripts/i18n check-i18n-style I18N_DIRS=packages/service-library
```


## Rediscover I18N_DIRS

Run this from the repo root to see which dirs currently contain `user_message()` calls and compare with `I18N_DIRS` in the Makefile:

```bash
grep -r 'user_message(' services packages --include='*.py' -l \
  | xargs -I{} dirname {} | sort -u
```

**Note:** The old qooxdoo extraction method is still available via `make -C services/static-webserver/client qx-extract` (DEPRECATED, for fallback only).

## Validation

```bash
make -C scripts/i18n check-i18n-style
```

Checks that no `user_message()` calls use f-strings (f-strings break xgettext extraction).

## Cleanup

```bash
make -C scripts/i18n clean   # removes regenerable artifacts only: _partials/, *.pot, *.mo
```

The versioned `.po` files (reviewed translations) are **never** deleted by `clean`.


## Open in a PO editor

Any standard `.po` editor works — the `CTX-*` fields appear as normal translator
comments and are fully editable:

```markdown
- [**Poedit**](https://poedit.net) — GUI, shows `CTX-SNIPPET` and `CTX-INTERPRETATION` in the sidebar
- [**Gtranslator**](https://wiki.gnome.org/Apps/Gtranslator) — GNOME desktop editor
- [**Virtaal**](http://virtaal.translatehouse.org) — lightweight cross-platform option
- [**VS Code**](https://code.visualstudio.com) — plugins as [*i18n Ally*](https://marketplace.visualstudio.com/items?itemName=lokalise.i18n-ally)
```

## References

- [GNU `gettext` utilities](https://www.gnu.org/software/gettext/manual/html_node/index.html)
- [`polib` library](https://github.com/izimobil/polib)
