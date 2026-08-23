"""The ``[tool.cmake2md]`` table of a ``pyproject.toml``.

A CI step that renders three templates needs six paired arguments to say so,
and they have to be kept in step across a Makefile, a workflow file and a
pre-commit hook.  A config file says it once.

``tomli`` reads it on every version.  The standard library grew the same
parser as ``tomllib`` in 3.11, but reaching for whichever of the two is
present would mean a version check and a branch that only the oldest
interpreter in the test matrix ever runs — a poor trade against one small
dependency with nothing under it.
"""

import enum
import pathlib
from typing import Any

import tomli

from . import doc_parser
from . import tag_lexer
from .errors import UsageError

#: Where the settings live, and the file they live in by default.
DEFAULT_FILE = 'pyproject.toml'
TABLE = 'tool.cmake2md'


class Kind(enum.Enum):
    """The value a setting has to have.

    Named after the type rather than after the shape, because that is what
    has to be checked: ``strict = "no"`` is a string, and every non-empty
    string is true, so a setting left unchecked reads as the opposite of what
    it says.
    """

    Bool = 'bool'
    Str = 'str'
    List = 'list'
    #: The [tool.cmake2md.tags] sub-table, which declares tags of the
    #: project's own.
    Tags = 'tags'


#: Settings the file may carry.  Anything else in the table is a mistake worth
#: pointing out rather than ignoring.
KEYS = {
    'template': Kind.List,
    'output': Kind.List,
    'template_dir': Kind.List,
    'path': Kind.List,
    'exclude': Kind.List,
    'json': Kind.Str,
    'inject': Kind.Bool,
    'strict': Kind.Bool,
    'check': Kind.Bool,
    'require_docs': Kind.Bool,
    'tags': Kind.Tags,
}

#: What a tag's own table may say, beyond which nothing is guessed at.
TAG_KEYS = frozenset({'text', 'takes_name', 'label'})
#: A custom tag holds text; a flag or a label would have nowhere on the parsed
#: comment to be stored, so those stay built-in.
TAG_TEXTS = (doc_parser.TagText.Paragraph, doc_parser.TagText.Block)


def load(path: pathlib.Path) -> dict[str, Any]:
    """Read the [tool.cmake2md] table of `path`.

    An empty result means the file has nothing to say about cmake2md, which
    is not an error: a project may keep a pyproject.toml for other reasons.
    """
    try:
        data = tomli.loads(path.read_text(encoding='utf-8'))
    except OSError as exc:
        raise UsageError(f'cannot read {path}: {exc.strerror}') from exc
    except tomli.TOMLDecodeError as exc:
        raise UsageError(f'{path} is not valid TOML: {exc}') from exc

    where = f'{path}: [{TABLE}]'
    table = data.get('tool', {}).get('cmake2md', {})
    if not isinstance(table, dict):
        raise UsageError(f'{where} must be a table')

    settings: dict[str, Any] = {}
    for key, value in table.items():
        name = key.replace('-', '_')
        if name not in KEYS:
            known = ', '.join(sorted(KEYS))
            raise UsageError(
                f'{where} has no setting called {key}; the settings are: {known}'
            )
        match KEYS[name]:
            case Kind.Bool:
                settings[name] = _as_bool(where, key, value)
            case Kind.Str:
                settings[name] = _as_str(where, key, value)
            case Kind.List:
                settings[name] = _as_list(where, key, value)
            case Kind.Tags:
                settings[name] = _as_tags(f'{path}: [{TABLE}.tags]', value)
    return settings


def _as_str(where: str, key: str, value: Any) -> str:
    if not isinstance(value, str):
        raise UsageError(f'{where} {key} must be a string')
    return value


def _as_list(where: str, key: str, value: Any) -> list[str]:
    """Accept a lone string where a list is expected, as TOML users expect."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return list(value)
    raise UsageError(f'{where} {key} must be a string or a list of them')


def _as_tags(where: str, value: Any) -> dict[str, doc_parser.TagSpec]:
    """Read [tool.cmake2md.tags] as the vocabulary the parser understands."""
    if not isinstance(value, dict):
        raise UsageError(f'{where} must be a table, one entry per tag')

    specs = {}
    for name, settings in value.items():
        specs[name] = _as_tag(where, name, settings)
    return specs


def _as_tag(where: str, name: str, settings: Any) -> doc_parser.TagSpec:
    if not _is_tag_name(name):
        raise UsageError(
            f'{where} {name} is not a name a tag can have: a tag is written '
            '@ and a letter or _, then letters, digits and _'
        )
    if name in doc_parser.TAG_SPECS:
        raise UsageError(f'{where} @{name} is already a tag of cmake2md')
    if not isinstance(settings, dict):
        raise UsageError(
            f'{where} {name} must be a table, as in '
            f'{name} = {{ label = "{name.capitalize()}:" }}'
        )

    unknown = set(settings) - TAG_KEYS
    if unknown:
        raise UsageError(
            f'{where} {name} has no setting called {sorted(unknown)[0]}; '
            f'a tag takes: {", ".join(sorted(TAG_KEYS))}'
        )

    here = f'{where} {name}:'
    return doc_parser.TagSpec(
        target=doc_parser.TagTarget.Section,
        takes_name=_as_bool(here, 'takes_name', settings.get('takes_name', False)),
        text=_as_text(where, name, settings.get('text', 'paragraph')),
        # Without a label of its own the tag is its own label, which reads
        # well enough for the @author and @rationale sort of tag.
        label=_as_str(here, 'label', settings.get('label') or f'{name.capitalize()}:'),
    )


def _is_tag_name(name: str) -> bool:
    """Whether the lexer would read '@name' as one whole tag."""
    match = tag_lexer.TAG_RE.fullmatch('@' + name)
    return match is not None


def _as_bool(where: str, key: str, value: Any) -> bool:
    """A flag, and nothing that merely reads as one.

    TOML has a boolean, so a string here is a mistake — and one that would
    otherwise pass silently, since 'no' and 'false' are both true.
    """
    if not isinstance(value, bool):
        raise UsageError(f'{where} {key} must be true or false')
    return value


def _as_text(where: str, name: str, value: Any) -> doc_parser.TagText:
    """How much of the text after the tag is the tag's own.

    A custom tag has to hold text: there is nowhere on the parsed comment for
    a flag or a label of the project's own devising to be stored.
    """
    allowed = [text.value for text in TAG_TEXTS]
    if value not in allowed:
        raise UsageError(
            f'{where} {name}: text must be one of {", ".join(allowed)}, not {value!r}'
        )
    return doc_parser.TagText(value)
