---
applyTo: '**'
---
Provide project context and coding guidelines that AI should follow when generating code, answering questions, or reviewing changes.

## General Guidelines

1. **Test-Driven Development**: Write unit tests for all new functions and features.
2. **Environment Variables**: Use [Environment Variables Guide](../../docs/env-vars.md) for configuration. Avoid hardcoding sensitive information.
3. **Documentation**: Prefer self-explanatory code; add documentation only if explicitly requested by the developer. Be concise. Do not copy paste documentation around or put in NOTE. Use docstrings for functions and classes if not self explanatory, and provide examples when necessary.
4. **Code Reviews**: Participate in code reviews and provide constructive feedback.
5. **Localization (i18n)**: Use `user_message()` for all user-facing strings. See [i18n Guide](../../scripts/i18n/README.md) for extraction, translation, and compilation pipeline.
6. **Alphabetical Ordering**: Keep all unordered lists in alphabetical order unless the order carries semantic meaning (e.g. dependency ordering, priority). This applies to: pip requirement files (e.g. `_test.in`, `_base.in`), `__all__` declarations, imports groups, registry/mapping entries, and any other enumerations where sequence is otherwise arbitrary.
