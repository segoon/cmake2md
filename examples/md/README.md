# Markdown example

[`CMakeLists.txt`](CMakeLists.txt) is a small documented CMake project;
[`reference.md.jinja`](reference.md.jinja) is a generic template that turns it
into [`reference.md`](reference.md), a Markdown reference with function and
macro sections and grouped option tables.

From the repository root:

```shell
cmake2doc \
    --template examples/md/reference.md.jinja \
    --output examples/md/reference.md \
    examples/md/CMakeLists.txt
```

Things worth looking at in the template:

- `symbol.pretty` renders a function or macro with the built-in
  `function.md.jinja`.
- `symbols | documented` drops `_example_internal_helper`, which has no doc
  comment of its own, and `symbol.type_` splits functions from macros.
- `commands | only_command('option') | only_group('build')` selects the
  `option()` calls tagged `# @ingroup build`.
- `only_group(None)` collects the options that carry no `@ingroup` tag.
- `md_escape` keeps descriptions from breaking the Markdown tables, and
  `escape` quotes defaults such as `${CMAKE_SOURCE_DIR}`.

The CMake source also exercises a few parsing details on purpose: a description
containing `maintainer@example.com` (not a tag), an escaped `@@` sign, an
`@@ingroup` mentioned in prose rather than used as a tag, and a comment block
ended by a blank line. This is the example the test suite asserts on, so those
details live here rather than being spread across the other two.
