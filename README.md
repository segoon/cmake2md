# cmake2md

Documentation generator for CMake. It parses CMake sources with
[tree-sitter](https://tree-sitter.github.io/), extracts doxygen-like comments
from `function()` definitions and command calls, and renders them through your
own [Jinja](https://jinja.palletsprojects.com/) templates.

Nothing about the output format is baked in: cmake2md hands your template a
parsed model of the file and gets out of the way.

## Installation

```shell
pip install cmake2md
```

Requires Python 3.10 or newer.

## Quick start

Document a function with `@`-tags in the comment block directly above it:

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

Render it:

```shell
cmake2md --template reference.md.jinja --output docs/reference.md CMakeLists.txt
```

With the built-in template that function becomes:

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

A complete, runnable example lives in [`examples/`](examples/).

## Comment syntax

A doc comment is the run of `#` comment lines immediately above a `function()`
or a command call. A blank line ends the run.

| Tag | Applies to | Meaning |
|-----|------------|---------|
| `@arg NAME` | function | Positional argument. Always required. |
| `@option NAME` | function | Valueless flag. |
| `@param NAME` | function | Keyword taking a single value. |
| `@multiparam NAME` | function | Keyword taking one or more values. |
| `@required` | function | Marks the *preceding* parameter as required. |
| `@ingroup NAME` | function, command | Assigns the symbol to a group. |

Text that is not part of a tag becomes the description: text before the first
parameter tag describes the symbol, text after a parameter tag describes that
parameter.

An `@` only starts a tag at the beginning of a line or after whitespace, so
`maintainer@example.com` stays literal. Write `@@` for a literal `@` at the
start of a word. Tags that cmake2md does not recognise are left in the text
and reported as warnings; pass `--strict` to turn them into errors instead.

### Adding a tag

The vocabulary is deliberately small and lives in one place:
`TAG_SPECS` in [`src/cmake2md/doc_parser.py`](src/cmake2md/doc_parser.py).
Register the tag there and handle it in `Parser._handle_tag`.

## Writing templates

Templates receive two lists:

- `symbols` — every documented `function()`
- `commands` — every top-level command call (`option()`, `set()`, …)

Each entry is a dict with:

| Key | Description |
|-----|-------------|
| `name` | Function or command name. |
| `doc` | Parsed comment: `.description`, `.group`, `.args`, `.options`, `.params`, `.multi_params`. |
| `group` | Shorthand for `doc.group`, i.e. the `@ingroup` value or `None`. |
| `pretty` | Function rendered via `function.md.jinja`; for commands, the plain description. |
| `comments` | The raw comment lines. |
| `args` | Commands only: the raw argument list, e.g. `['FOO', '"desc"', 'ON']`. |
| `filepath`, `line`, `location` | Where the symbol was found. |

Each parameter in `doc.args` / `doc.options` / `doc.params` / `doc.multi_params`
has `.name`, `.description`, `.required` and `.kind`.

### Filters

| Filter | Purpose |
|--------|---------|
| `unquote` | Strip surrounding double quotes from a CMake argument. |
| `escape` | Quote a value containing `$` so it does not read as a variable reference. |
| `md_escape` | Escape `\|` and `\` so a string is safe inside a Markdown table cell. |
| `oneline` | Join CMake line continuations. |
| `only_command(name)` | Keep only commands with the given name. |
| `only_group(name)` | Keep only entries in the given `@ingroup` (use `None` for ungrouped). |
| `render` | Concatenate the `pretty` field of a collection. |

### The built-in template

`symbol.pretty` is produced by the packaged `function.md.jinja`. Put a file of
that name in a `--template-dir` (or the working directory) to replace it.

It also works as a whole document on its own, which documents every function
and needs no template of your own:

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
| `-o`, `--output` | Where to write the matching `--template`. Repeatable, paired in order. |
| `-I`, `--template-dir` | Extra directory to search for templates. Repeatable. |
| `--strict` | Treat unknown `@tags` as errors. |
| `--check` | Write nothing; exit non-zero if any output is missing or stale. |

`--check` is meant for CI, to verify that generated documentation was
regenerated after a change to the CMake sources.

## Development

```shell
make install    # pip install -e '.[dev]'
make check      # lint, type check and test, as CI does
```

`make help` lists the rest: `test`, `lint`, `format`, `typecheck`, `example`
(regenerate `examples/reference.md`), `dist` and `clean`.

## License

Apache License 2.0 — see [LICENSE](LICENSE) and [NOTICE](NOTICE).
cmake2md started life as a set of scripts inside the
[userver](https://github.com/userver-framework/userver) framework.
