"""The ``cmake2md.toml`` a project keeps beside its CMake code.

A CI step that renders three templates needs six paired arguments to say so,
and they have to be kept in step across a Makefile, a workflow file and a
pre-commit hook.  A config file says it once.

The settings are the whole file: it is cmake2md's own, so it needs no table
to say whose settings these are.  A relative path in it is relative to the
file, which is the only reading that survives being run from a subdirectory.

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

#: The --output/--json value that means "write to stdout" instead of to a
#: file.  Defined here, and re-exported by `cli`, so that a path setting
#: resolved against the config file (`_against`) knows to leave it alone.
STDOUT = '-'
#: The file the settings live in, looked for from the working directory up.
DEFAULT_FILE = 'cmake2md.toml'
#: What stops that search: past a repository, the file would not be this
#: project's own any more.
ROOT_MARKERS = ('.git',)


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
    #: The [tags] sub-table, which declares tags of the project's own.
    Tags = 'tags'


#: Settings the file may carry.  Anything else in it is a mistake worth
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

#: Settings that name a file, and so are read relative to the config file.
#: 'exclude' is not one: it is a glob matched against a source path, not a
#: path itself.
PATH_KEYS = frozenset({'output', 'path', 'template_dir', 'json'})
#: A template is either a path or the name of a built-in, told apart the way
#: rendering.resolve_template_spec tells them apart: by whether the file is
#: there.  Only the path sort is read against the config file.
TEMPLATE_KEYS = frozenset({'template'})

#: What a tag's own table may say, beyond which nothing is guessed at.
TAG_KEYS = frozenset({'text', 'takes_name', 'label'})
#: A custom tag holds text; a flag or a label would have nowhere on the parsed
#: comment to be stored, so those stay built-in.
TAG_TEXTS = (doc_parser.TagText.Paragraph, doc_parser.TagText.Block)


def find(start: pathlib.Path) -> pathlib.Path | None:
    """The nearest config file at or above `start`, if there is one.

    A project is configured once, at its root, but its commands are run from
    wherever is convenient — a build directory, a subdirectory being worked
    on.  The search stops at a repository, since a file above one belongs to
    something else.
    """
    for directory in (start, *start.parents):
        candidate = directory / DEFAULT_FILE
        if candidate.is_file():
            return candidate
        if any((directory / marker).exists() for marker in ROOT_MARKERS):
            return None
    return None


def load(path: pathlib.Path) -> dict[str, Any]:
    """Read the settings `path` holds, which are the whole of it.

    An empty result means the file says nothing, which is not an error: a
    project may keep one for the sake of the tags alone.
    """
    try:
        data = tomli.loads(path.read_text(encoding='utf-8'))
    except OSError as exc:
        raise UsageError(f'cannot read {path}: {exc.strerror}') from exc
    except tomli.TOMLDecodeError as exc:
        raise UsageError(f'{path} is not valid TOML: {exc}') from exc

    where = f'{path}:'
    root = path.parent
    settings: dict[str, Any] = {}
    for key, value in data.items():
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
                settings[name] = _as_tags(f'{path}: [tags]', value)
        if name in PATH_KEYS:
            settings[name] = _against(root, settings[name])
        elif name in TEMPLATE_KEYS:
            settings[name] = _against(root, settings[name], only_if_file=True)
    return settings


def _against(root: pathlib.Path, value: Any, only_if_file: bool = False) -> Any:
    """Read a path the config file gives as relative to the file itself.

    Anything else would depend on where cmake2md happened to be run from,
    which is exactly what a config file at the project root is there to stop
    mattering.  `STDOUT` is not a path at all, and must be left alone:
    resolving it against a directory would create a file called `-` instead
    of writing to standard output.
    """
    if isinstance(value, list):
        return [_against(root, item, only_if_file) for item in value]
    if value == STDOUT:
        return value
    resolved = root / value
    if only_if_file and not resolved.is_file():
        return value
    return str(resolved)


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
    """Read the [tags] table as the vocabulary the parser understands."""
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
            f'{name} = {{ label = "{_capitalized(name)}:" }}'
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
        label=_as_str(here, 'label', settings.get('label') or f'{_capitalized(name)}:'),
    )


def _capitalized(name: str) -> str:
    """Uppercase the first letter of `name`, leaving the rest as written.

    str.capitalize() would also lowercase the rest, turning a tag such as
    @myTag into the label 'Mytag:' rather than 'MyTag:'.
    """
    return name[:1].upper() + name[1:]


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
