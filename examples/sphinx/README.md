# Sphinx example

[`reference.rst.jinja`](reference.rst.jinja) renders
[`CMakeLists.txt`](CMakeLists.txt) into Sphinx's CMake domain — the one
CMake's own documentation is built with — rather than into plain
reStructuredText.

From the repository root:

```shell
cmake2doc \
    --template examples/sphinx/reference.rst.jinja \
    --output examples/sphinx/reference.rst \
    examples/sphinx/CMakeLists.txt
```

Each symbol becomes a `.. cmake:command::` directive, which Sphinx puts in the
index and which `:cmake:command:`example_fail`` links to from anywhere in the
site; cache variables become `.. cmake:variable::`. The domain has no
directive for a function as distinct from a macro — to CMake both are commands
— so both use the same one.

The domain is not part of Sphinx. Install it and switch it on:

```shell
pip install sphinxcontrib-moderncmakedomain
```

```python
# conf.py
extensions = ['sphinxcontrib.moderncmakedomain']
```

[`reference.rst`](reference.rst) will therefore **not** parse with plain
docutils, unlike [`../rest/reference.rst`](../rest/reference.rst): it uses
`versionadded`, `deprecated`, `code-block` and the domain directives, all of
which Sphinx provides. Nothing here is built in CI — the output is checked as
text.

`--inject` looks for an rST comment (`.. BEGIN_CMAKE2MD` / `.. END_CMAKE2MD`)
rather than an HTML one when the `--output` file ends in `.rst`, so this
template can be injected straight into a hand-written Sphinx source page the
same way the plain rST example injects into one:

```shell
cmake2doc --inject \
    --template examples/sphinx/reference.rst.jinja \
    --output docs/reference.rst \
    examples/sphinx/CMakeLists.txt
```
