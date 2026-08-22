"""Jinja environment, template resolution and the filters templates may use."""

import pathlib
import re
from typing import Any
from typing import Iterable
from typing import Sequence

import jinja2

#: Name of the template used to render each function into ``symbol.pretty``.
#: Shadowing this file from a `--template-dir` overrides the built-in one.
FUNCTION_TEMPLATE_NAME = 'function.md.jinja'

_FENCE_RE = re.compile(r'^```.*?^```', re.MULTILINE | re.DOTALL)


def unquote(s: str) -> str:
    """Strip the surrounding double quotes of a quoted CMake argument."""
    return s.removesuffix('"').removeprefix('"')


def escape(s: str) -> str:
    """Quote a CMake value that would otherwise read as a variable reference."""
    if '$' in s:
        return f'"{s}"'
    return s


def md_escape(s: str) -> str:
    """Make a string safe to drop into a Markdown table cell."""
    return s.replace('\\', '\\\\').replace('|', '\\|').replace('\n', ' ')


def oneline(s: str) -> str:
    """Join a CMake line continuation into a single line."""
    return s.replace('\\\n', ' ')


def render(collection: Iterable[dict]) -> str:
    return ''.join(item['pretty'] + '\n' for item in collection)


def only_command(collection: Iterable[dict], name: str) -> list[dict]:
    return [item for item in collection if item['name'] == name]


def only_group(collection: Iterable[dict], name: str | None) -> list[dict]:
    return [item for item in collection if item.get('group') == name]


FILTERS = {
    'unquote': unquote,
    'escape': escape,
    'md_escape': md_escape,
    'oneline': oneline,
    'only_group': only_group,
    'only_command': only_command,
    'render': render,
}


def collapse_blank_lines(text: str) -> str:
    """Collapse runs of blank lines, leaving fenced code blocks untouched."""

    def squeeze(chunk: str) -> str:
        return re.sub(r'\n{3,}', '\n\n\n', chunk)

    out = []
    pos = 0
    for m in _FENCE_RE.finditer(text):
        out.append(squeeze(text[pos : m.start()]))
        out.append(m.group())
        pos = m.end()
    out.append(squeeze(text[pos:]))
    return ''.join(out)


def resolve_template_spec(spec: str) -> tuple[pathlib.Path | None, str]:
    """Split a template argument into a search directory and a template name.

    A spec that names an existing file is loaded from its own directory, so
    that ``{% include %}`` next to it keeps working.  Anything else is looked
    up by name in the search path and, finally, among the built-in templates.
    """
    path = pathlib.Path(spec)
    if path.is_file():
        return path.parent, path.name
    return None, spec


def build_environment(search_dirs: Sequence[pathlib.Path]) -> jinja2.Environment:
    loader = jinja2.ChoiceLoader([
        jinja2.FileSystemLoader([str(d) for d in search_dirs]),
        jinja2.PackageLoader('cmake2md', 'templates'),
    ])
    env = jinja2.Environment(
        loader=loader,
        autoescape=False,
        keep_trailing_newline=True,
    )
    env.filters.update(FILTERS)
    return env


def render_document(template: jinja2.Template, context: dict[str, Any]) -> str:
    return collapse_blank_lines(template.render(context)).strip() + '\n'
