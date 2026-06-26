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

```bash
# Run from repo root or any directory
make -C scripts/i18n all
```

## Step-by-Step

| Step | Target               | Description                                                                 |
| ---- | -------------------- | --------------------------------------------------------------------------- |
| 1    | `extract-all`        | Scan `I18N_DIRS` for `user_message()` + frontend for `this.tr()` → `.pot`s  |
| 2    | `merge`              | `msgcat` backend partials + frontend → `messages.pot`, then enrich with CTX |
| 3    | `translate`          | AI translate stale backend entries (one `.po` per `LANG`)                   |
| 4    | `compile`            | `msgfmt` backend `.po` → `.mo`                                              |
| 5    | `frontend-translate` | AI translate frontend entries from master template                          |

```bash
make -C scripts/i18n extract-all
make -C scripts/i18n merge
make -C scripts/i18n translate
make -C scripts/i18n compile
make -C scripts/i18n frontend-translate
```

## Key Variables

| Variable      | Default         | Description                               |
| ------------- | --------------- | ----------------------------------------- |
| `LANGS`       | `zh_CN es_ES`   | Space-separated locale codes to translate |
| `MODEL`       | `openai/gpt-4o` | LiteLLM model string                      |
| `BASE_URL`    | _(empty)_       | Custom LLM endpoint (e.g. local Ollama)   |
| `PARALLEL`    | `false`         | Enable parallel translation workers       |
| `MAX_WORKERS` | `4`             | Worker count when `PARALLEL=true`         |
| `USE_GIT`     | `true`          | Skip already-committed translations       |

## Provider Shortcuts

```bash
make -C scripts/i18n translate-openai      # OpenAI gpt-4o
make -C scripts/i18n translate-anthropic   # Anthropic claude-sonnet-4-6
make -C scripts/i18n translate-ollama      # local Ollama llama3.1 (no API key)
make -C scripts/i18n translate-custom MODEL=mistral/mistral-large BASE_URL=http://localhost:4000
```

## Override Language or Model Inline

```bash
make -C scripts/i18n all LANGS="de_DE fr_FR"
make -C scripts/i18n translate MODEL=anthropic/claude-sonnet-4-6
```

## Per Service / Package

There is no dedicated per-service target. Override `I18N_DIRS` to scope extraction or validation to one service or package:

```bash
# Extract only one service
make -C scripts/i18n extract-all I18N_DIRS=services/api-server

# Validate style for one package
make -C scripts/i18n check-i18n-style I18N_DIRS=packages/service-library
```

After scoped extraction, run `merge` to rebuild `messages.pot` from all partials.

## Rediscover I18N_DIRS

Run this from the repo root to see which dirs currently contain `user_message()` calls and compare with `I18N_DIRS` in the Makefile:

```bash
grep -r 'user_message(' services packages --include='*.py' -l \
  | xargs -I{} dirname {} | sort -u
```

## Frontend

Frontend extraction is now handled by xgettext (same as backend). Extraction happens as part of `make extract-all`:

```bash
make -C scripts/i18n extract-all                        # extracts backend + frontend
make -C scripts/i18n extract-frontend                   # frontend only (for testing)
make -C scripts/i18n translate-frontend                 # translate from master template
make -C scripts/i18n translate-frontend CLIENT_LANGS="de_DE"   # specific language
```

Frontend `.po` files are output to: `services/static-webserver/client/source/translation/{lang}.po`

**Note:** The old qooxdoo extraction method is still available via `make -C services/static-webserver/client qx-extract` (DEPRECATED, for fallback only).

## Validation

```bash
make -C scripts/i18n check-i18n-style
```

Checks that no `user_message()` calls use f-strings (f-strings break xgettext extraction).

## Cleanup

```bash
make -C scripts/i18n clean   # removes _partials/, messages.pot, frontend.pot, all .po and .mo
```


## Open in a PO editor

Any standard `.po` editor works — the `CTX-*` fields appear as normal translator
comments and are fully editable:

- **Poedit** — GUI, shows `CTX-SNIPPET` and `CTX-INTERPRETATION` in the sidebar
- **Gtranslator** — GNOME desktop editor
- **Virtaal** — lightweight cross-platform option
- **VS Code** — install the *i18n Ally* or *gettext* extension for inline review
