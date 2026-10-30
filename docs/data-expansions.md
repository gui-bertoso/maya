# Data Expansions

Containers in `data/expansions/DataExpansionN.myde` extend Maya without changing
the main processor. `.myde` means **Maya Data Expansion**: a UTF-8 file containing
JSON, designed to remain readable and editable.

```json
{
  "format": "maya-data-expansion",
  "format_version": 1,
  "name": "package-name",
  "version": 1,
  "commands": {
    "asks_joke": ["another way to ask for a joke"]
  },
  "responses": {
    "asks_joke_en": ["an additional response"]
  }
}
```

## Behavior

- Files are discovered automatically and loaded in numeric order: `0`, `1`, `2`, and so on.
- Each `.myde` must declare `format` and `format_version`; unknown versions are safely rejected.
- Older `.json` containers remain supported, but new packages should use `.myde`.
- Duplicate commands and responses are removed during merging.
- An invalid container is skipped without preventing others from loading.
- Changes are detected during use, at most one second after a file is saved.
- Adding content to an existing intent does not require editing `core/process.py`.

The intent name must exist in the processor's `patterns` dictionary. New
functionality still requires code; additional phrasing and responses do not.
