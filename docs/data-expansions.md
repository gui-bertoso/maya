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

## Queryable knowledge

A `.myde` may also declare `knowledge` alongside `commands` and `responses`:

```json
{
  "format": "maya-data-expansion",
  "format_version": 1,
  "name": "example",
  "version": 1,
  "knowledge": [{
    "questions": ["what is a python list", "explain python list"],
    "answer": "Lists hold ordered items and can be changed after creation.",
    "sources": [{"title": "Python data structures", "url": "https://docs.python.org/3/tutorial/datastructures.html"}]
  }]
}
```

Queries are normalized, exact lookups, not free-form generation. Different
questions require explicit aliases. Sources are mandatory; package text is never
executed. `source` displays sources for the latest record. Personal learning takes
priority over packaged knowledge for the same question; corrections do not modify
the distributed file. Removing a package removes its knowledge after refresh
without deleting personal memory.

Each container is validated completely before use. Invalid sections or sources
reject the entire package rather than partially publishing aliases. A question
conflicting with an earlier package rejects the later package and records an
error in `expansion_loader.errors`.

DataExpansion4–8 cover Python, Godot, Git, Linux files/paths, and computing/web.
They include 100 English records and 600 aliases linked to primary documentation.
Examples: `what is python list`, `explain godot signal`, `what is git staging area`,
`linux inode`, `what is javascript event loop`.
