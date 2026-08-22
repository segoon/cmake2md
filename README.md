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

While cmake2md is at 0.x, the tag vocabulary and the values handed to
templates may still change; pin `cmake2md~=0.1` if you generate documentation
in CI.

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

That function becomes:

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

Only `#` line comments are doc comments. A bracket comment (`#[[ ... ]]`) is
ignored, and a symbol documented that way reads as undocumented.

| Tag | Applies to | Meaning |
|-----|------------|---------|
| `@arg NAME` | function, macro | Positional argument. Always required. |
| `@option NAME` | function, macro | Valueless flag. |
| `@param NAME` | function, macro | Keyword taking a single value. |
| `@multiparam NAME` | function, macro | Keyword taking one or more values. |
| `@return NAME` | function, macro | Variable set in the caller's scope: CMake's way of returning a value. |
| `@required` | function, macro | Marks the *preceding* parameter as required. |
| `@ingroup NAME` | function, macro, command | Assigns the symbol to a group. |
| `@deprecated` | function, macro, command | Marks the whole symbol as deprecated. Text after it stays in the description, where it reads as the reason. |

Text that is not part of a tag becomes the description: text before the first
parameter tag describes the symbol, text after a parameter tag describes that
parameter.

An `@` only starts a tag at the beginning of a line or after whitespace, so
`maintainer@example.com` stays literal. Write `@@` for a literal `@` at the
start of a word — for instance when prose mentions a tag, as in
`not tagged with @@ingroup`.

Two things are left in the text and reported as warnings rather than acted on:
a tag cmake2md does not recognise, and a known tag that is not followed by
something that looks like a name (`@ingroup, so …` is prose, not a group named
`,`). Pass `--strict` to turn both into errors.

### Checking the comment against the code

A CMake function states its interface twice — once in the doc comment, once in
its own body — and the two drift apart. cmake2md reads the second one and
reports the disagreement:

```cmake
# @option QUIET be quiet
# @multiparam SRCS the source files
function(example_add_library)
    cmake_parse_arguments(ARG "QUIET" "" "SOURCES" ${ARGN})
endfunction()
```

```
CMakeLists.txt:2: function example_add_library: warning: SRCS is documented as
@multiparam but example_add_library does not accept it
CMakeLists.txt:3: function example_add_library: warning: example_add_library
takes SOURCES but it is not documented; add @multiparam SOURCES
```

Four things are read out of the code: both call forms of
`cmake_parse_arguments()`, the named parameters of `function(f NAME TYPE)`,
`set(VAR ... PARENT_SCOPE)` and `return(PROPAGATE VAR)` — the last two being
what `@return` documents.

What the code does not state plainly is never guessed at, and so never warned
about. A keyword list built from a variable, a body with two
`cmake_parse_arguments()` calls in it, a macro that reaches for `${ARGV0}`, or
an output variable whose name the caller supplies
(`set(${ARG_OUTPUT_VARIABLE} ... PARENT_SCOPE)`) all leave the matching tags
unchecked. Symbols with no doc comment at all are not reported either.

`--strict` turns these warnings into errors as well.

### Adding a tag

The vocabulary is deliberately small and lives in one place:
`TAG_SPECS` in
[`src/cmake2md/doc_parser.py`](https://github.com/segoon/cmake2md/blob/master/src/cmake2md/doc_parser.py).
Register the tag there and handle it in `Parser._handle_tag`.

## Writing templates

Templates receive three lists:

- `symbols` — every `function()` and `macro()`, documented or not
- `variables` — every cache entry a user can set: `option()` and
  `set(... CACHE ...)`, parsed
- `commands` — every command call (`option()`, `set()`, …), including calls
  nested in a `function()` body or an `if()` block

All three are unfiltered on purpose: the `documented` filter drops the
entries that carry no comment, and `only_command` selects the commands you
actually document.

Each entry is a dict with:

| Key | Description |
|-----|-------------|
| `name` | Function, macro or command name. |
| `doc` | Parsed comment: `.description`, `.group`, `.deprecated`, `.args`, `.options`, `.params`, `.multi_params`, `.returns`, `.warnings`. |
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
| `filepath`, `line`, `location` | Where the symbol was found. |

Each parameter in `doc.args` / `doc.options` / `doc.params` /
`doc.multi_params` / `doc.returns` has `.name`, `.description`, `.required`,
`.kind` and `.line`.

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
| `render` | Concatenate the `pretty` field of a collection. |

### The built-in template

`symbol.pretty` is produced by the packaged `function.md.jinja`. Put a file of
that name in a `--template-dir` (or the working directory) to replace it.

It also works as a whole document on its own, which documents every documented
function and macro and needs no template of your own:

```sh
cmake2md --template function.md.jinja --output docs/functions.md CMakeLists.txt
```

## Command line

```
cmake2md [-t TEMPLATE -o OUTPUT]... [-I DIR]... [--strict] [--check] CMAKE_FILE...
```

| Flag | Effect |
|------|--------|
| `-t`, `--template` | Template to render: a path, or the name of a built-in. Repeatable. |
| `-o`, `--output` | Where to write the matching `--template`, or `-` for stdout. Repeatable, paired in order. |
| `-I`, `--template-dir` | Extra directory to search for templates. Repeatable. |
| `--strict` | Treat documentation warnings as errors: a doubtful `@tag`, or a comment that disagrees with the code. |
| `--check` | Write nothing; exit non-zero if any output is missing or stale. |
| `--list-templates` | List the built-in template names and exit. |
| `--version` | Print the version and exit. |

Each `CMAKE_FILE` is a file, a directory to search for `CMakeLists.txt` and
`*.cmake` (dot-directories are skipped), or a glob pattern. cmake2md expands
directories and patterns itself, so it behaves the same in shells that do not,
such as those on Windows.

`--check` is meant for CI, to verify that generated documentation was
regenerated after a change to the CMake sources.

## Development

```shell
make install    # pip install -e '.[dev]'
make check      # lint, type check and test, as CI does
```

`make help` lists the rest: `test`, `lint`, `format`, `typecheck`, `example`
(regenerate `examples/reference.md`), `dist`, `clean` and, for maintainers,
`release-check`, `publish-test` and `publish`.

Every pull request runs `make check example-check` on Linux, the test suite on
Linux, macOS and Windows for each supported Python version, and a packaging
smoke test. The `ci-ok` job summarises all of them; it is the single check to
require in the branch protection rule, so that changing the test matrix never
means editing that rule.

## License

Apache License 2.0 — see
[LICENSE](https://github.com/segoon/cmake2md/blob/master/LICENSE) and
[NOTICE](https://github.com/segoon/cmake2md/blob/master/NOTICE).
cmake2md started life as a set of scripts inside the
[userver](https://github.com/userver-framework/userver) framework.
