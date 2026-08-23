# cmake2md

[![CI](https://github.com/segoon/cmake2md/actions/workflows/ci.yml/badge.svg)](https://github.com/segoon/cmake2md/actions/workflows/ci.yml)

Documentation generator for CMake. It parses CMake sources with
[tree-sitter](https://tree-sitter.github.io/), extracts doxygen-like comments
from `function()` definitions and command calls, and renders them through your
own [Jinja](https://jinja.palletsprojects.com/) templates.

Nothing about the output format is baked in: cmake2md hands your template a
parsed model of the file and gets out of the way.

## Installation

```shell
pip install cmake2md      # or: pipx install cmake2md
```

Requires Python 3.10 or newer.

## Quick start

Document a function (or a macro) with `@`-tags in the comment block directly
above it:

```cmake
# Adds a library target together with its tests and install rules.
#
# @arg NAME the name of the resulting target
# @option EXCLUDE_FROM_ALL do not build this target by default
# @param OUTPUT_NAME @required file name of the produced artifact
# @multiparam SOURCES the source files to compile
function(example_add_library)
endfunction()
```

Render it with the built-in template:

```shell
cmake2md --template function.md.jinja --output docs/reference.md CMakeLists.txt
```

That function becomes `docs/reference.md`:

````markdown
## example_add_library

Adds a library target together with its tests and install rules.

```
example_add_library(
    <NAME>
    [EXCLUDE_FROM_ALL]
    OUTPUT_NAME <value>
    [SOURCES <value>...]
)
```

* <**NAME**> the name of the resulting target
* **EXCLUDE_FROM_ALL** do not build this target by default
* **OUTPUT_NAME <value>** file name of the produced artifact
* **SOURCES <value>...** the source files to compile
````

A complete, runnable example lives in
[`examples/`](https://github.com/segoon/cmake2md/tree/master/examples).

## Comment syntax

A doc comment is the run of `#` comment lines immediately above a `function()`,
a `macro()` or a command call. A blank line ends the run. The block is dedented
as a whole, so the space in the conventional `# ` disappears while indentation
*inside* the comment — nested lists, code blocks — is preserved.

Both cmake comment forms carry documentation. A bracket comment works the same way,
including the `#[==[.rst:` style CMake's own modules use, where the `.rst:`
marker and the `#` of the closing `#]==]` are punctuation rather than text:

```cmake
#[==[.rst:
@brief Adds a library target.
#]==]
function(example_add_library)
endfunction()
```

| Tag | Applies to | Meaning |
|-----|------------|---------|
| `@arg NAME` | function, macro | Positional argument. Always required. |
| `@option NAME` | function, macro | Valueless flag. |
| `@param NAME` | function, macro | Keyword taking a single value. |
| `@multiparam NAME` | function, macro | Keyword taking one or more values. |
| `@set_parent_scope NAME` | function, macro | Variable the symbol sets in its caller's scope, which is how CMake hands a result back. |
| `@required` | function, macro | Marks the *preceding* parameter as required. |
| `@type NAME` | function, macro | What the *preceding* parameter's value should be. |
| `@default VALUE` | function, macro | What the *preceding* parameter is worth when left out. |
| `@ingroup NAME` | function, macro, command | Assigns the symbol to a group. |
| `@defgroup NAME <title>` | a comment block of its own | Defines a group: its title is the rest of the line, its description the paragraphs below. |
| `@file` | a comment block of its own | Marks the block as documenting the file it is in. |
| `@deprecated` | function, macro, command | Marks the whole symbol as deprecated. Text after it stays in the description, where it reads as the reason. |
| `@internal` | function, macro, command | Marks the symbol as not part of the public interface. The `public` filter drops it. |
| `@brief` | anything | A one-paragraph summary, distinct from the description. |
| `@example` | anything | A sample, held as a block so blank lines inside it survive. Checked to parse as CMake. |
| `@note`, `@warning` | anything | A paragraph set apart from the description. |
| `@since`, `@todo`, `@see` | anything | A paragraph each: a version, a task, a cross-reference. |

A tag that carries prose — `@brief`, `@note`, `@warning`, `@since`, `@todo`,
`@see` — ends at a blank line, as Doxygen's do, and what follows the blank
line belongs to the description again. `@example` and the parameter tags run
to the next tag instead, so a sample or a parameter description may span
paragraphs.

`doc.brief` is a plain string; the rest arrive as `doc.sections`, in the order
they were written, and `doc.of_kind('note')` selects one kind of them.

Text that is not part of a tag becomes the description: text before the first
parameter tag describes the symbol, text after a parameter tag describes that
parameter.

An `@` only starts a tag at the beginning of a line or after whitespace, so
`maintainer@example.com` stays literal. Write `@@` for a literal `@` at the
start of a word — for instance when prose mentions a tag, as in
`not tagged with @@ingroup`.

Two things are left in the text and reported rather than acted on: a tag
cmake2md does not recognise, and a known tag that is not followed by something
that looks like a name (`@ingroup, so …` is prose, not a group named `,`).
Both fail the run; pass `--no-strict` to have them reported as warnings and
carry on.

### Checking the comment against the code

A CMake function states its interface twice — once in the doc comment, once in
its own body — and the two drift apart. cmake2md reads the second one and
fails the run on the disagreement:

```cmake
# @option QUIET be quiet
# @multiparam SRCS the source files
function(example_add_library)
    cmake_parse_arguments(ARG "QUIET" "" "SOURCES" ${ARGN})
endfunction()
```

```
cmake2md: error: CMakeLists.txt:2: function example_add_library: SRCS is
documented as @multiparam but example_add_library does not accept it
```

Under `--no-strict` the run carries on and every disagreement is reported:

```
CMakeLists.txt:2: function example_add_library: warning: SRCS is documented as
@multiparam but example_add_library does not accept it
CMakeLists.txt:3: function example_add_library: warning: example_add_library
takes SOURCES but it is not documented; add @multiparam SOURCES
```

Four things are read out of the code:

- both call forms of `cmake_parse_arguments()`
- the named parameters of `function(f NAME TYPE)`
- `set(VAR ... PARENT_SCOPE)`
- `return(PROPAGATE VAR)`

The last two being what `@set_parent_scope` documents.

What the code does not state plainly is never guessed at, and so never warned
about. A keyword list built from a variable, a body with two
`cmake_parse_arguments()` calls in it, a macro that reaches for `${ARGV0}`, or
an output variable whose name the caller supplies
(`set(${ARG_OUTPUT_VARIABLE} ... PARENT_SCOPE)`) all leave the matching tags
unchecked. Symbols with no doc comment at all are not reported either.

An `@example` is checked the same way: it is CMake, so cmake2md parses it and
reports a sample that does not parse. Prose or another language belongs in a
fenced code block, which is left alone unless it is fenced as `cmake`.

`--no-strict` demotes these to warnings as well.

### Adding a tag

The vocabulary is deliberately small and lives in one place, as data:
`TAG_SPECS` in
[`src/cmake2md/doc_parser.py`](https://github.com/segoon/cmake2md/blob/master/src/cmake2md/doc_parser.py),
where each tag declares what it attaches to — a parameter, a section, a field
of the comment, a field of the parameter above it. Adding one is adding a row;
[DEVELOPMENT.md](DEVELOPMENT.md) has the table.

## Writing templates

Templates receive five lists:

- `symbols` — every `function()` and `macro()`, documented or not
- `variables` — every cache entry a user can set: `option()` and
  `set(... CACHE ...)`, parsed
- `commands` — every command call (`option()`, `set()`, …), including calls
  nested in a `function()` body or an `if()` block
- `groups` — every `@defgroup`, in the order they were defined, each with a
  `name`, a `title` and a `description`
- `files` — the `@file` comment blocks, each with the `doc` of the block

They are unfiltered on purpose: the `documented` filter drops the entries
that carry no comment, `public` drops the ones marked `@internal`, and
`only_command` selects the commands you actually document.

Each entry is a dict with:

| Key | Description |
|-----|-------------|
| `name` | Function, macro or command name. |
| `doc` | Parsed comment: `.description`, `.brief`, `.group`, `.deprecated`, `.internal`, `.args`, `.options`, `.params`, `.multi_params`, `.returns`, `.sections`, `.warnings`, and the `.of_kind(kind)` method. |
| `group` | Shorthand for `doc.group`, i.e. the `@ingroup` value or `None`. |
| `pretty` | Symbol rendered via `function.md.jinja`; for commands, the plain description. |
| `comments` | The raw comment lines, dedented. |
| `comments_line` | Line the comment block starts on, or `0` when there is none. |
| `type_` | Symbols: `'function'` or `'macro'`. |
| `signature` | Symbols only: what the code itself accepts, as `signature.accepts.arg`, `.option`, `.param`, `.multiparam` and `.return`. Each is a list of names, or `None` where the code does not say. |
| `args` | Commands only: the raw argument list, e.g. `['FOO', '"desc"', 'ON']`. |
| `command` | Variables only: `'option'` or `'set'`. |
| `type_` | Variables: the cache type, `BOOL`, `PATH`, `FILEPATH`, `STRING` or `INTERNAL`. |
| `default` | Variables only: the value the entry holds unless the user overrides it. |
| `docstring` | Variables only: the help string the command itself gives, which is what `cmake-gui` shows. |
| `choices` | Variables only: the values `set_property(CACHE … PROPERTY STRINGS …)` restricts the entry to, or `None`. |
| `advanced` | Variables only: whether `mark_as_advanced()` hides it from the ordinary user. |
| `filepath`, `line`, `location` | Where the symbol was found. |

Each parameter in `doc.args` / `doc.options` / `doc.params` /
`doc.multi_params` / `doc.returns` has `.name`, `.description`, `.required`,
`.kind`, `.line`, and `.type_` and `.default` from `@type` and `@default`.
Each entry of `doc.sections` has `.kind` — the tag that opened it, without the
`@` — `.text`, `.name` and `.line`.

### Groups

`@ingroup` puts a symbol in a group; `@defgroup`, in a comment block that
documents nothing else, gives that group a title and a description:

```cmake
# @defgroup build Build targets
#
# What gets built, and what is left out.
```

They arrive as `groups`, in the order they were defined, so a template writes
the whole document without naming a single group:

```jinja
{% for group in groups %}
## {{ group.title }}

{{ group.description }}

{{ render(symbols | documented | only_group(group.name)) }}
{% endfor %}
```

Once any group is defined, an `@ingroup` naming one that is not is reported —
until then `@ingroup` is a bare label, which is how it worked before, and
nothing is checked.

### Build options

`option(NAME "help" ON)` and `set(NAME value CACHE TYPE "help")` declare the
same thing in a different order, so `variables` gives both of them one shape:

```jinja
| Option | Description | Default |
|--------|-------------|---------|
{%- for v in variables | only_group('build') %}
| `{{ v.name }}` | {{ v.docstring | md_escape }} | `{{ v.default }}` |
{%- endfor %}
```

A `set()` that writes no cache entry is a local variable rather than something
to configure, so it is not in the list; it is still in `commands`. A
`set_property(CACHE … PROPERTY STRINGS …)` in the same file fills `choices`.

### Filters

| Filter | Purpose |
|--------|---------|
| `unquote` | Strip surrounding double quotes from a CMake argument. |
| `escape` | Quote a value containing `$` so it does not read as a variable reference. |
| `md_escape` | Escape `\|` and `\` so a string is safe inside a Markdown table cell. |
| `oneline` | Join CMake line continuations. |
| `only_command(name)` | Keep only commands with the given name. |
| `only_group(name)` | Keep only entries in the given `@ingroup` (use `None` for ungrouped). |
| `documented` | Keep only entries that carry a doc comment. |
| `public` | Drop the entries marked `@internal`. |
| `anchor` | The anchor a Markdown heading holding the given text gets. |
| `symbol_link(symbols)` | Link a name to its own section when `symbols` defines it, else leave it as written. |
| `render` | Concatenate the `pretty` field of a collection. |

### The built-in templates

Two templates ship with cmake2md, and `--list-templates` names them.

`reference.md.jinja` is a whole document: a table of contents, every
documented function and macro laid out by `@defgroup`, and a table of the
build options. A project that wants documentation without writing a template
needs only:

```sh
cmake2md --template reference.md.jinja --output docs/reference.md .
```

`function.md.jinja` renders a single symbol, and is what fills
`symbol.pretty`; put a file of that name in a `--template-dir` (or the working
directory) to change how every symbol is rendered. It also works as a whole
document, listing every documented symbol and nothing else.

## Command line

```
cmake2md [-t TEMPLATE -o OUTPUT]... [-I DIR]... [-c FILE] [--inject]
         [--json OUTPUT] [--exclude PATTERN]... [--require-docs]
         [--no-strict] [--check] CMAKE_FILE...
```

| Flag | Effect |
|------|--------|
| `-t`, `--template` | Template to render: a path, or the name of a built-in. Repeatable. |
| `-o`, `--output` | Where to write the matching `--template`, or `-` for stdout. Repeatable, paired in order. |
| `-I`, `--template-dir` | Extra directory to search for templates. Repeatable. |
| `-c`, `--config` | Read the arguments from the `[tool.cmake2md]` table of a TOML file. |
| `--inject` | Write between the markers of an existing `--output` file instead of replacing it. |
| `--json` | Also write the parsed model as JSON, for tools that are not templates. |
| `--exclude` | Skip sources matching a glob, against the whole path or the file name. Repeatable. |
| `--require-docs` | Exit non-zero if a public `function()` or `macro()` has no doc comment. |
| `--no-strict` | Report documentation problems — a doubtful `@tag`, or a comment that disagrees with the code — as warnings rather than failing the run, which is what it does by default. |
| `--check` | Write nothing; exit non-zero if any output is missing or stale. |
| `--list-templates` | List the built-in template names and exit. |
| `--version` | Print the version and exit. |

Each `CMAKE_FILE` is a file, a directory to search for `CMakeLists.txt` and
`*.cmake` (dot-directories are skipped), or a glob pattern. cmake2md expands
directories and patterns itself, so it behaves the same in shells that do not,
such as those on Windows.

`--check` is meant for CI, to verify that generated documentation was
regenerated after a change to the CMake sources; it prints a diff of what
differs, since nobody in CI can re-run the generator to find out.

`--require-docs` is the other CI gate, the equivalent of rustdoc's
`missing_docs`: a public symbol with no doc comment fails the run. A name
starting with `_` is private by CMake convention, and `@internal` says so
outright; neither is required to be documented.

A `.cmake2mdignore` file in the working directory lists further `--exclude`
patterns, one per line, `#` starting a comment.

### The config file

A CI step that renders three templates needs six paired arguments to say so,
and they then have to be kept in step across a Makefile, a workflow file and a
pre-commit hook. Say it once instead, in `pyproject.toml`:

```toml
[tool.cmake2md]
template = ["reference.md.jinja"]
output = ["docs/reference.md"]
path = ["."]
require-docs = true
```

and the CI step is `cmake2md` with nothing after it. Every long option has a
setting of the same name, with `-` or `_` between words, and a lone string is
accepted where a list belongs. Anything given on the command line wins over
the file, so `cmake2md --output - .` still prints to the terminal — and a flag
turned off explicitly counts as given, so `--no-strict` wins over a
`strict = true` in the file.

`pyproject.toml` is read when it has a `[tool.cmake2md]` table; `--config`
names a different file, which must then exist.

### Injecting into a README

`--inject` keeps the documentation inside a file the author writes, rather
than in one of its own. Mark the place once:

```markdown
# My project

<!-- BEGIN_CMAKE2MD -->
<!-- END_CMAKE2MD -->
```

and everything between the markers is replaced on each run, leaving the prose
around them alone. It composes with `--check`.

### JSON

`--json` writes the same model a template is given:

```json
{
  "schema_version": 1,
  "symbols": [{"name": "example_add_library", "doc": {"brief": "…"}}],
  "variables": [], "commands": [], "groups": [], "files": []
}
```

`schema_version` is bumped when a field disappears or changes meaning, never
when one is added, so a consumer must ignore the fields it does not know.

## From CMake

`cmake/cmake2md.cmake` adds targets that run cmake2md as part of the build, so
a project documents its own CMake code without a separate script to remember.
Copy it into your module path, or fetch it:

```cmake
include(cmake2md)

cmake2md_generate(
    # `cmake --build build --target docs` regenerates the documentation.
    # A second target, `docs-check`, verifies instead that it is up to date
    # and fails with a diff when it is not, which is what a CI job wants.
    TARGET docs
    # A path, or the name of a built-in template.
    TEMPLATE reference.md.jinja
    # Written into the source tree, since it is committed.
    OUTPUT ${CMAKE_CURRENT_SOURCE_DIR}/docs/reference.md
    # The CMake files to read; the current source directory when omitted.
    SOURCES cmake/helpers.cmake
    # Anything else cmake2md takes.
    EXTRA_ARGS --require-docs
    # Build `docs` as part of the default build.
    ALL
)
```

The module is documented with cmake2md's own tags, so it also serves as a
worked example.

## In CI

A pre-commit hook:

```yaml
repos:
  - repo: https://github.com/segoon/cmake2md
    rev: v0.1.0
    hooks:
      - id: cmake2md-check
        args: [--template, reference.md.jinja, --output, docs/reference.md, .]
```

`cmake2md-check` fails when the documentation is out of date and shows what
differs; `cmake2md` regenerates it instead, so the commit picks it up.

A GitHub Action:

```yaml
- uses: segoon/cmake2md@v0.1.0
  with:
    args: --check --template reference.md.jinja --output docs/reference.md .
```

## Development

See [DEVELOPMENT.md](DEVELOPMENT.md): the workflow, how the modules fit
together, and how to add a tag.

## Prior art

cmake2md is a Markdown generator for CMake with a checking pass, which is a
gap between two neighbourhoods rather than new ground:

| | |
|---|---|
| [Doxygen](https://www.doxygen.nl/) | Where the `@tag` vocabulary comes from, down to a paragraph tag ending at a blank line. It has no CMake parser. |
| [CMinx](https://github.com/CMakePP/CMinx) | The other CMake documentation generator. It derives signatures from the grammar as cmake2md does, and emits reStructuredText for Sphinx rather than Markdown. |
| CMake's own [Sphinx domain](https://github.com/Kitware/CMake/blob/master/Help/dev/documentation.rst) | Where the `#[==[.rst:` comment style comes from, and how CMake's own modules are documented. |
| [terraform-docs](https://terraform-docs.io/), [helm-docs](https://github.com/norwoodj/helm-docs) | The same problem for another declarative language: a typed table of inputs, injection into an existing README, a config file, a pre-commit hook. |
| [rustdoc](https://doc.rust-lang.org/rustdoc/) | Doc examples that are checked rather than trusted, and `missing_docs` — here `@example` and `--require-docs`. |
| [shdoc](https://github.com/reconquest/shdoc) | The same shape of problem for shell: a dynamic language whose interface is only stated in comments. |

Where cmake2md differs from all of them is the checking pass: the doc comment
is compared against what the CMake code actually accepts, and the two are
reported when they disagree.

## License

Apache License 2.0 — see
[LICENSE](https://github.com/segoon/cmake2md/blob/master/LICENSE) and
[NOTICE](https://github.com/segoon/cmake2md/blob/master/NOTICE).
cmake2md started life as a set of scripts inside the
[userver](https://github.com/userver-framework/userver) framework.
