# TODO

Ordered roadmap. The rationale, and the comparison with the documentation
generators of other languages that produced it, are in the plan this list came
from; the short version is that cmake2md derives nothing from the code and
hands templates raw argument lists, which is where every comparable tool
(CMinx, terraform-docs, helm-docs, Doxygen, rustdoc) is ahead of it.

## Housekeeping

- split out README.md -> DEVELOPMENT.md
- integrate cmake2md into CMakeLists.txt
- @return -> @set_parent_scope
- add "inspired by": doxygen, ...
- compare with alternatives from other languages

## P1 — Source-derived signatures (done)

- [x] read the keywords declared by `cmake_parse_arguments()`, both call forms
- [x] read the positional parameters declared by `function(f NAME TYPE)`
- [x] warn when the doc comment and the code disagree; `--strict` fails
- [x] output variables: `set(X ... PARENT_SCOPE)` and `return(PROPAGATE X)`,
      documented with `@return`

## P2 — Typed model for commands (done)

- [x] `option()` and `set(... CACHE ...)` parsed into records (name, type,
      default, docstring, `STRINGS` choices) exposed as a `variables` context
      list
- [x] retire the positional `cmd.args[0]` / `cmd.args[4]` indexing in
      `examples/reference.md.jinja`
- [x] keep `commands` as it is, for templates that already use it
- [ ] `mark_as_advanced()`, the CMake way of saying a variable is not for
      ordinary users — the same shape of work as `choices`

## P3 — Tag vocabulary

`TagSpec` now carries a `TagText` mode, so a tag that only holds prose needs a
`TAG_SPECS` entry and nothing else.

- [x] `@brief` — a summary distinct from the body, for index tables
- [x] `@example`, with the snippet checked to parse as CMake, which is as
      close to rustdoc's doc tests as CMake allows
- [x] `@since`, `@note`, `@warning`, `@todo`, `@see`
- [x] `@internal` — hide a private helper deliberately rather than by the
      accident of it having no comment
- [ ] stable anchors and auto-linking of symbol names, so `@see` becomes a
      link rather than a name
- [x] `@defgroup NAME <title>` with a description and an ordering, so
      `examples/reference.md.jinja` stops hardcoding the group names
- [ ] parameter types and default values
- [ ] file-level documentation (`@file`)

## P4 — Output and CI integration

- JSON dump of the model, as a stable versioned schema
- inject into an existing README between markers, as terraform-docs does
- config file: `[tool.cmake2md]` in `pyproject.toml`, instead of N paired
  `--template`/`--output` arguments in CI (`tomllib` is stdlib on 3.11+, so
  only 3.10 needs a fallback — ask before adding the dependency)
- `--require-docs`: fail on an undocumented public symbol, like rustdoc's
  `missing_docs`
- show a diff in `--check` instead of only "out of date"
- `--exclude` and an ignore file
- a `reference.md.jinja` built-in with a table of contents, so a project needs
  no template of its own
- a pre-commit hook and a GitHub Action

## P5 — Parsing

- bracket comments (`#[[ ... ]]`), including CMake's own `#[[.rst:` style:
  today a symbol documented that way silently reads as undocumented

## Decided against

Recorded so they are not revisited: reStructuredText/Sphinx output (CMinx and
upstream CMake cover it), `@copydoc`, following `include()` and
`add_subdirectory()`, HTML themes, a client-side search index.
