# Changelog

## Unreleased

### Fixed

- A tag that takes a name (`@ingroup`, `@type`, `@default`, `@defgroup`,
  the parameter tags) no longer reaches past its own line's end to find one;
  a tag left with nothing after it but a newline reports the existing
  "requires a name" error instead of silently taking the next line's first
  word as its name.
- `output = "-"` and `json = "-"` in `cmake2md.toml`, which mean "write to
  stdout", are no longer resolved against the config file's directory into a
  file literally called `-`.
- A diagnostic about an `option()` or `set(... CACHE ...)` call is no longer
  printed twice, once as a `Command` and once as the `Variable` it also is;
  it is reported once, under the `Variable`'s own name.
- A source file reached twice — a directory and an explicit path both
  matching it, or the same argument given twice — is read once instead of
  documenting every symbol in it twice over.
- A second `@brief` or `@ingroup` in one doc comment is a warning, and the
  first is kept, instead of silently overwriting it. A `@defgroup` naming a
  group a previous one already defined is likewise a warning, and only the
  first defines the group; previously the section was rendered twice.

### Added

- Tags a project declares itself, in the `[tags]` table of the config file. A
  declared tag opens a section like `@note` does — `text`, `takes_name` and
  `label` say how — so it is recognised rather than reported,
  reachable as `doc.of_kind('author')`, and rendered by the built-in template
  under its label without anyone writing a template.
- `cmake/cmake2md.cmake`, a module whose `cmake2md_generate(TARGET docs)` adds
  two build targets that run cmake2md — one that writes the documentation and
  a `-check` companion that verifies it — so a CMake project can document
  itself from its own build. `TARGET` is all it takes: the rest is in
  `cmake2md.toml`, and a target that repeated any of it would be a second
  place to keep in step. It is written with cmake2md's own tags, and the test
  suite holds it to `--strict`.
- A config file: the nearest `cmake2md.toml` at or above the working
  directory, or any TOML file named with `--config`, so a CI step is
  `cmake2md` and nothing else. A relative path in it is relative to the file,
  so the run means the same thing from a build directory as from the project
  root. The command line always wins over it.
- Bracket comments (`#[[ … ]]`) document a symbol like `#` comments do,
  including CMake's own `#[==[.rst:` house style. A symbol documented that way
  used to read as undocumented, silently.
- `mark_as_advanced()` sets `advanced` on a variable, which is CMake's own way
  of saying an entry is not one an ordinary user reaches for.
- `--inject` writes between the `<!-- BEGIN_CMAKE2MD -->` and
  `<!-- END_CMAKE2MD -->` markers of an existing file, so generated
  documentation can live inside a hand-written README. It composes with
  `--check`.
- A second built-in template, `reference.md.jinja`: a whole document with a
  table of contents, laid out by `@defgroup`, so a project needs no template
  of its own.
- A pre-commit hook (`cmake2md-check` and `cmake2md`) and a GitHub Action.
- `--json OUTPUT` writes the parsed model as JSON, under a `schema_version`
  that is bumped only when a field disappears or changes meaning.
- `--require-docs` fails the run on a public `function()` or `macro()` with no
  doc comment, like rustdoc's `missing_docs`. A leading `_` and `@internal`
  both mean private.
- `--exclude PATTERN`, repeatable, and a `.cmake2mdignore` file listing more
  of the same.
- `@type` and `@default` refine the parameter written above them, as
  `@required` already did, and the built-in template prints them.
- `@file`, in a comment block of its own, marks that block as documenting the
  file; those blocks arrive as the `files` list.
- `anchor` and `symbol_link` filters, so a `@see` naming a symbol the document
  defines becomes a link to it and one naming anything else stays prose. The
  built-in template links them.
- `@defgroup NAME <title>`, written in a comment block of its own, gives a
  group a title, a description and a position in the document. Templates get
  them as `groups`, so `examples/reference.md.jinja` no longer names a single
  group of its own. An `@ingroup` naming a group that no `@defgroup` defines
  is reported, once any group is defined at all.
- Comment blocks that document nothing are extracted, which is where a group
  is defined and where anything said about the file as a whole will go.
- Eight tags: `@brief`, `@example`, `@note`, `@warning`, `@since`, `@todo`
  and `@see`. A prose tag holds one paragraph and ends at a blank line, as
  Doxygen's does; `@example` holds a block, so the blank lines inside a sample
  survive. They arrive as `doc.brief` and `doc.sections`, which
  `doc.of_kind('note')` selects from, and the built-in template renders them.
- `@example` is checked to parse as CMake — the closest a build language gets
  to rustdoc's doc tests. A sample in a fence naming another language is left
  alone.
- `@internal` marks a symbol as not part of the public interface, and the new
  `public` filter drops those. It gives a private helper a way to be hidden
  deliberately rather than by the accident of having no comment.
- `variables`, a third list templates are rendered with: every cache entry a
  user can set, from `option()` and from `set(... CACHE ...)`, parsed into
  `name`, `type_`, `default`, `docstring` and `choices`. A template no longer
  has to know the argument order of either command, nor that the help string
  is the second argument of one and the fifth of the other. `choices` comes
  from `set_property(CACHE ... PROPERTY STRINGS ...)`.
- The parameters a `function()` or `macro()` accepts are read from its own
  code: the named parameters of `function(f NAME TYPE)` and the keyword lists
  of `cmake_parse_arguments()`, in both of its call forms. Templates see them
  as `symbol.signature`.
- A doc comment that disagrees with the code it documents is reported: a
  documented parameter the definition does not take, one documented as the
  wrong kind, one the definition takes but the comment omits, and a name
  documented twice. Anything the code does not state plainly — a keyword list
  built from a variable, two `cmake_parse_arguments()` calls, a macro reading
  `${ARGV0}` — is left unchecked rather than guessed at.
- `@return NAME` documents a variable the definition sets in its caller's
  scope, which is how CMake returns a value. The built-in template renders
  them, and they are checked against the `set(VAR ... PARENT_SCOPE)` and
  `return(PROPAGATE VAR)` calls in the body — except when the caller supplies
  the variable's name, which the code cannot reveal.
- Each parameter records the line of the tag that introduced it, as `.line`.

### Dependencies

- `tomli`, to read the config file. The standard library has the same parser
  as `tomllib` from 3.11 on, but taking whichever is present would mean a
  version check and a branch that only the oldest supported interpreter runs.

### Changed

- The tag vocabulary is data: every tag declares what it attaches to — a
  parameter, a section, a field of the comment, a field of the parameter above
  it — and the parser names no tag of its own. `doc.sections` entries carry a
  `.label` as a result.
- `@return` is now `@set_parent_scope`, which is what it documents: CMake's
  `return()` does something else entirely.
- `--check` prints a diff of what differs instead of only reporting that
  something does.
- `--strict` now promotes every documentation warning to an error, not only a
  doubtful `@tag`, and it is what a run does by default: a documentation
  problem nobody is made to look at is a documentation problem nobody fixes.
  `--no-strict`, or `strict = false` in the config file, reports them as
  warnings and carries on.
- A flag turned off on the command line now beats the config file, which used
  to win over it because "off" and "unsaid" were the same value.
- A config setting of the wrong type is refused rather than taken as it comes.
  `strict = "no"` used to turn strict *on*, every non-empty string being true;
  now it says so. The lists were already checked; the rest were not.

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
- `@deprecated` marks a whole symbol as deprecated; the built-in template
  renders it, and the text after the tag stays in the description as the
  reason.
- A `CMAKE_FILE` argument may be a directory, which is searched for
  `CMakeLists.txt` and `*.cmake`, or a glob pattern. Both are expanded by
  cmake2md, so shells that do not expand globs — Windows' — behave the same.
- `--list-templates` prints the packaged template names.
- `--output -` writes to stdout.
- `--check` verifies that generated documentation is up to date without
  writing, for use in CI.
- `md_escape` filter for Markdown table cells.
- `@@` escape for a literal `@`.
- Errors and warnings report the file, line and symbol they came from, and
  the line is the one the offending tag is on rather than the line of the
  definition below it.
- A name defined by more than one of the sources read is reported, naming both
  definitions.
- Two `--template` options writing to one `--output` is a usage error instead
  of silently discarding one of the two renders.
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
- A `function()` or `macro()` whose name is quoted (`function("foo")`) is no
  longer dropped from the documentation without a word.
- A command called without arguments (`enable_testing()`) is no longer dropped
  together with its doc comment.
- A comment inside an argument list is no longer taken for an argument.
- `unquote` leaves an unpaired `"` alone instead of stripping it.
