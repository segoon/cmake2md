# TODO

## Redundancy and duplication

* The context entry is `dict[str, Any]` throughout `cli`, `rendering` and
  `serialize`, which is the `Any` the project's own rules rule out. A small
  dataclass with an `asdict()` would type the whole render path.

## Decided against

Recorded so they are not revisited: reStructuredText/Sphinx output (CMinx and
upstream CMake cover it), `@copydoc`, following `include()` and
`add_subdirectory()`, HTML themes, a client-side search index.
