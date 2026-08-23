# reStructuredText example

[`CMakeLists.txt`](CMakeLists.txt) rendered with the **built-in**
`reference.rst.jinja` — there is no template in this directory, which is the
point: the built-in is named rather than written.

From the repository root:

```shell
cmake2md \
    --template reference.rst.jinja \
    --output examples/rest/reference.rst \
    examples/rest/CMakeLists.txt
```

The output, [`reference.rst`](reference.rst), uses only directives docutils
itself understands — `code`, `note`, `warning`, `admonition`, `list-table` —
so it parses with or without Sphinx:

```shell
python -m docutils examples/rest/reference.rst /dev/null
```

To pull it into a Sphinx project, generate it into your source directory and
reference it from a toctree like any other page. If you want Sphinx's CMake
domain — indexed commands, and `:cmake:command:` cross-references — see
[`../sphinx/`](../sphinx), which emits those directives instead.

Note that `symbol.pretty` is Markdown, always: it is rendered by
`function.md.jinja`. A template that emits anything else has to lay symbols
out from `doc.args`, `doc.params` and the rest itself, as the built-in
reStructuredText template does.
