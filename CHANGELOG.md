# Changelog

## 0.1.0 (2026-08-22)

First release as a standalone project, extracted from the
[userver](https://github.com/userver-framework/userver) build scripts.

### Added

- Installable `cmake2md` package and console script, published on PyPI.
- `macro()` definitions are documented alongside `function()` ones; templates
  tell them apart with `symbol.type_`.
- `documented` filter, so templates can leave out symbols and commands that
  carry no doc comment. The built-in `function.md.jinja` uses it.
- `--version`.
- Templates are resolved from `--template-dir`, the working directory and the
  packaged built-ins, so projects can ship their own without vendoring
  cmake2md. The built-in `function.md.jinja` can be shadowed to change how
  `symbol.pretty` is rendered, and can itself be passed to `--template` to
  document every function without writing a template.
- `@ingroup` now works on functions as well as commands; `only_group` applies
  uniformly to `symbols` and `commands`.
- `--strict` turns unknown tags into errors; by default they are kept as
  literal text and reported as warnings.
- `--check` verifies that generated documentation is up to date without
  writing, for use in CI.
- `md_escape` filter for Markdown table cells.
- `@@` escape for a literal `@`.
- Errors report the file, line and symbol they came from.
- `Makefile` wrapping the development workflow (`make help` for the list).

### Changed

- The `--template TEMPLATE:OUTPUT` syntax is replaced by paired
  `--template TEMPLATE --output OUTPUT` options, which also works for paths
  containing a colon.
- Templates access the parsed comment as `symbol.doc` rather than
  `symbol.prototype`.
- Output is always written as UTF-8 with `\n` line endings, and missing parent
  directories are created.
- Comment blocks are dedented as a whole, so the space in the conventional
  `# ` no longer offsets the first line from the rest and indentation inside a
  comment survives.

### Fixed

- An `@` in ordinary prose (for example an e-mail address) is no longer lexed
  as a tag, which previously aborted the whole run.
- Tag names are no longer truncated at `_` or a digit (`@param_x`).
- A tag with a missing name reports an error instead of raising a bare
  `StopIteration`.
- `@required` before any parameter tag is an error instead of being silently
  ignored.
- A blank line now ends a comment block, so an unrelated comment further up the
  file is not absorbed into a symbol's documentation.
- Blank-line collapsing no longer reformats fenced code blocks.
- `tag_lexer` used invalid string escapes, which are a `SyntaxWarning` on
  Python 3.12 and an error under `-W error`.
- A known tag merely mentioned in prose ("not tagged with `@ingroup`, so …")
  no longer swallows the punctuation after it as a name; it is kept as literal
  text and reported, like an unknown tag.
- A CMake file that is not valid UTF-8 is reported with its file and line
  instead of aborting with a `UnicodeDecodeError` traceback.
- A missing template says which directories were searched and which built-in
  templates exist, instead of printing just the template name.
