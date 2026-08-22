# Example

[`CMakeLists.txt`](CMakeLists.txt) is a small documented CMake project;
[`reference.md.jinja`](reference.md.jinja) is a generic template that turns it
into a Markdown reference with a function section and grouped option tables.

From the repository root:

```shell
cmake2md \
    --template examples/reference.md.jinja \
    --output examples/reference.md \
    examples/CMakeLists.txt
```

Things worth looking at in the template:

- `symbol.pretty` renders a function with the built-in `function.md.jinja`.
- `commands | only_command('option') | only_group('build')` selects the
  `option()` calls tagged `# @ingroup build`.
- `only_group(None)` collects the options that carry no `@ingroup` tag.
- `md_escape` keeps descriptions from breaking the Markdown tables, and
  `escape` quotes defaults such as `${CMAKE_SOURCE_DIR}`.

The CMake source also exercises two parsing details on purpose: a description
containing `maintainer@example.com` (not a tag) and an escaped `@@` sign.
