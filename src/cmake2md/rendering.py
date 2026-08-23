"""Jinja environment, template resolution and the filters templates may use."""

import pathlib
import re
from collections.abc import Iterable
from collections.abc import Sequence
from typing import Any

import jinja2

from .errors import UsageError

#: Markers that delimit the generated part of a file written with --inject.
INJECT_BEGIN = '<!-- BEGIN_CMAKE2MD -->'
INJECT_END = '<!-- END_CMAKE2MD -->'

#: Name of the template used to render each function into ``symbol.pretty``.
#: Shadowing this file from a `--template-dir` overrides the built-in one.
FUNCTION_TEMPLATE_NAME = 'function.md.jinja'

#: A fenced code block: ``` optionally followed by a language name, then the
#: body, then a closing ```. Named groups, so `checks.cmake_snippets` can pull
#: the language and body apart while this module only needs the whole span.
FENCE_RE = re.compile(
    r'^```(?P<lang>\w*)[ \t]*\n(?P<body>.*?)^```', re.MULTILINE | re.DOTALL
)

#: One entry of the `symbols` or `commands` list a template is rendered with,
#: as built by `cli.enrich`.
Item = dict[str, Any]


def unquote(s: str) -> str:
    """Strip the surrounding double quotes of a quoted CMake argument."""
    # Both quotes or neither: a lone '"' is part of the value, not a wrapper.
    if len(s) >= 2 and s.startswith('"') and s.endswith('"'):
        return s[1:-1]
    return s


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


def render(collection: Iterable[Item]) -> str:
    return ''.join(item['pretty'] + '\n' for item in collection)


def anchor(name: str) -> str:
    """The anchor a Markdown heading holding `name` gets.

    The rule is the one GitHub and most Markdown renderers use: lowercase,
    spaces to hyphens, everything else that is not a word character dropped.
    """
    return re.sub(r'[^\w-]', '', name.strip().lower().replace(' ', '-'))


def symbol_link(name: str, collection: Iterable[Item]) -> str:
    """Link `name` to its own section, if it is one of `collection`.

    A name that nothing in the document defines is left as it was written:
    a cross-reference to another project's function is still worth printing.
    """
    target = name.strip().removesuffix('()')
    if any(item['name'] == target for item in collection):
        return f'[{target}](#{anchor(target)})'
    return name


def only_command(collection: Iterable[Item], name: str) -> list[Item]:
    return [item for item in collection if item['name'] == name]


def only_group(collection: Iterable[Item], name: str | None) -> list[Item]:
    return [item for item in collection if item.get('group') == name]


def documented(collection: Iterable[Item]) -> list[Item]:
    """Keep only the entries that carry a doc comment."""
    return [item for item in collection if any(c.strip() for c in item['comments'])]


def public(collection: Iterable[Item]) -> list[Item]:
    """Drop the entries their author marked @internal."""
    return [
        item
        for item in collection
        if not (item.get('doc') is not None and item['doc'].internal)
    ]


FILTERS = {
    'unquote': unquote,
    'escape': escape,
    'md_escape': md_escape,
    'oneline': oneline,
    'only_group': only_group,
    'only_command': only_command,
    'documented': documented,
    'public': public,
    'render': render,
    'anchor': anchor,
    'symbol_link': symbol_link,
}


def collapse_blank_lines(text: str) -> str:
    """Cap runs of blank lines at two, leaving fenced code blocks alone.

    Templates that loop over symbols emit ragged vertical whitespace; two
    blank lines are enough to separate sections in Markdown.  Inside a fence
    the blank lines are content, so they are copied through as they are.
    """

    def squeeze(chunk: str) -> str:
        return re.sub(r'\n{3,}', '\n\n\n', chunk)

    out = []
    pos = 0
    for m in FENCE_RE.finditer(text):
        out.append(squeeze(text[pos : m.start()]))
        out.append(m.group())
        pos = m.end()
    out.append(squeeze(text[pos:]))
    return ''.join(out)


def resolve_template_spec(
    spec: str, cwd: pathlib.Path
) -> tuple[pathlib.Path | None, str]:
    """Split a template argument into a search directory and a template name.

    A spec that names an existing file is loaded from its own directory, so
    that ``{% include %}`` next to it keeps working.  Anything else is looked
    up by name in the search path and, finally, among the built-in templates.
    `cwd` is where a relative `spec` is read from; it has no effect on an
    absolute one, since `/` on an absolute right-hand side discards the left.
    """
    path = cwd / spec
    if path.is_file():
        return path.parent, path.name
    return None, spec


def builtin_loader() -> jinja2.PackageLoader:
    return jinja2.PackageLoader('cmake2md', 'templates')


def build_environment(search_dirs: Sequence[pathlib.Path]) -> jinja2.Environment:
    loader = jinja2.ChoiceLoader(
        [
            jinja2.FileSystemLoader([str(d) for d in search_dirs]),
            builtin_loader(),
        ]
    )
    env = jinja2.Environment(
        loader=loader,
        autoescape=False,
        keep_trailing_newline=True,
    )
    env.filters.update(FILTERS)
    return env


def load_template(
    env: jinja2.Environment, name: str, search_dirs: Sequence[pathlib.Path]
) -> jinja2.Template:
    """Load `name`, turning a miss into an error that says where we looked."""
    try:
        return env.get_template(name)
    except jinja2.TemplateNotFound as exc:
        # exc.name rather than `name`: the miss may come from an {% include %}.
        missing = exc.name or name
        searched = ', '.join(str(d) for d in search_dirs) or '(no directories)'
        builtins = ', '.join(sorted(builtin_loader().list_templates()))
        raise UsageError(
            f'template not found: {missing}\n'
            f'  searched: {searched}\n'
            f'  built-in templates: {builtins}'
        ) from None


def render_document(template: jinja2.Template, context: dict[str, Any]) -> str:
    # Whatever whitespace the template's control blocks leave at either end,
    # a document ends with exactly one newline and no leading blank lines.
    return collapse_blank_lines(template.render(context)).strip() + '\n'


def inject(existing: str, content: str, path: str) -> str:
    """Put `content` between the markers in `existing`, keeping the rest.

    This is how documentation lives inside a hand-written README instead of
    in a file of its own: the prose around the markers is the author's, and
    only what is between them is ours to replace.
    """
    begin = existing.find(INJECT_BEGIN)
    end = existing.find(INJECT_END)
    if begin == -1 or end == -1:
        raise UsageError(
            f'{path} has no place to inject into; it needs a line saying '
            f'{INJECT_BEGIN} and a later one saying {INJECT_END}'
        )
    if end < begin:
        raise UsageError(
            f'{path} has {INJECT_END} before {INJECT_BEGIN}, so there is '
            'nothing between them'
        )
    head = existing[: begin + len(INJECT_BEGIN)]
    return f'{head}\n{content.strip()}\n\n{existing[end:]}'
