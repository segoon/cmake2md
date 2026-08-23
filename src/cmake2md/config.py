"""The ``cmake2md.toml`` a project keeps beside its CMake code.

A CI step that renders three templates needs six paired arguments to say so,
and they have to be kept in step across a Makefile, a workflow file and a
pre-commit hook.  A config file says it once.

The settings are the whole file: it is cmake2md's own, so it needs no table
to say whose settings these are.  A relative path in it is relative to the
file, which is the only reading that survives being run from a subdirectory.

`Settings` is the single declaration of what the file may hold: the settings,
their types, and what each is worth when unsaid.  `cli` reads its defaults
from the same place, so the two cannot drift apart.
"""

import dataclasses
import pathlib
from typing import Annotated
from typing import Any

import pydantic
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

#: A custom tag holds text; a flag or a label would have nowhere on the parsed
#: comment to be stored, so those stay built-in.
TAG_TEXTS = (doc_parser.TagText.Paragraph, doc_parser.TagText.Block)

#: The one setting whose field cannot be named after it: see `Settings.json_`.
JSON_FIELD = 'json_'
JSON_SETTING = 'json'


@dataclasses.dataclass(frozen=True)
class AgainstConfigFile:
    """Marks a setting whose value names a file, and so is read relative to it.

    Carried as field metadata rather than in a table of its own, so that a
    setting says everything about itself in one place.  `only_if_file` is what
    tells a template path from the name of a built-in: by whether the file is
    there, the way `rendering.resolve_template_spec` tells them apart.
    """

    only_if_file: bool = False


def _check_tag_name(name: str) -> str:
    """A key of the [tags] table: a name a tag can have, and not one taken."""
    # A tag the lexer would not read as one whole tag could never be written.
    if tag_lexer.TAG_RE.fullmatch('@' + name) is None:
        raise ValueError(
            f'{name} is not a name a tag can have: a tag is written '
            '@ and a letter or _, then letters, digits and _'
        )
    if name in doc_parser.TAG_SPECS:
        raise ValueError(f'@{name} is already a tag of cmake2md')
    return name


#: A setting that takes several values.  Strict, item and all: TOML says what
#: a value is, so `path = [1]` is a mistake rather than something to read as
#: "1", and `path = "."` is a mistake rather than a list of one.
StrList = list[pydantic.StrictStr]
#: A key of the [tags] table.
TagName = Annotated[str, pydantic.AfterValidator(_check_tag_name)]


def _dashed(name: str) -> str:
    """The spelling of a setting on the command line: --require-docs."""
    return name.replace('_', '-')


class TagSettings(pydantic.BaseModel):
    """What a tag of the project's own may say about itself."""

    # No dashed aliases here, unlike `Settings`: a tag's settings are not
    # command-line options, and are documented as written.
    model_config = pydantic.ConfigDict(extra='forbid')

    #: How much of the text after the tag is the tag's own.  A custom tag has
    #: to hold text: there is nowhere on the parsed comment for a flag or a
    #: field of the project's own devising to be stored.
    text: doc_parser.TagText = doc_parser.TagText.Paragraph
    takes_name: pydantic.StrictBool = False
    label: pydantic.StrictStr | None = None

    @pydantic.field_validator('text')
    @classmethod
    def _text_holds_some(cls, value: doc_parser.TagText) -> doc_parser.TagText:
        if value not in TAG_TEXTS:
            allowed = ', '.join(text.value for text in TAG_TEXTS)
            raise ValueError(f'text must be one of {allowed}, not {value.value!r}')
        return value

    def to_spec(self, name: str) -> doc_parser.TagSpec:
        return doc_parser.TagSpec(
            target=doc_parser.TagTarget.Section,
            takes_name=self.takes_name,
            text=self.text,
            # Without a label of its own the tag is its own label, which reads
            # well enough for the @author and @rationale sort of tag.
            label=self.label or f'{_capitalized(name)}:',
        )


class Settings(pydantic.BaseModel):
    """The settings the file may carry, and what each is worth when unsaid.

    Anything else in it is a mistake worth pointing out rather than ignoring,
    which is what `extra='forbid'` says.  Every setting is also a long option,
    and is spelled here as that option is, so `require-docs` and
    `require_docs` both name this field.
    """

    model_config = pydantic.ConfigDict(
        extra='forbid', alias_generator=_dashed, populate_by_name=True
    )

    template: Annotated[StrList, AgainstConfigFile(only_if_file=True)] = []
    output: Annotated[StrList, AgainstConfigFile()] = []
    template_dir: Annotated[StrList, AgainstConfigFile()] = []
    path: Annotated[StrList, AgainstConfigFile()] = []
    #: Not a path but a glob matched against one, so it is left as written.
    exclude: StrList = []
    #: Trailing underscore because a field called `json` shadows a method of
    #: pydantic's own base class, which it warns about; `JSON_SETTING` puts
    #: the name back before anything outside this module sees it.
    json_: Annotated[
        pydantic.StrictStr | None,
        AgainstConfigFile(),
        pydantic.Field(validation_alias='json'),
    ] = None
    inject: pydantic.StrictBool = False
    check: pydantic.StrictBool = False
    require_docs: pydantic.StrictBool = False
    strict: pydantic.StrictBool = True
    tags: dict[TagName, TagSettings] = {}

    def as_arguments(self, *, only_set: bool = False) -> dict[str, Any]:
        """The settings under the names the command line knows them by.

        `only_set` leaves out everything the file did not name: `cli` tells an
        unsaid setting from one turned off on purpose by whether it is there
        at all, so a default filled in here would beat an explicit
        --no-strict.
        """
        dumped = self.model_dump(exclude_unset=only_set)
        if JSON_FIELD in dumped:
            dumped[JSON_SETTING] = dumped.pop(JSON_FIELD)
        if 'tags' in dumped:
            dumped['tags'] = {
                name: tag.to_spec(name) for name, tag in self.tags.items()
            }
        return dumped


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

    Only the settings the file actually names are returned: `cli` tells an
    unsaid setting from one turned off on purpose by whether it is there at
    all, so a default filled in here would beat an explicit --no-strict.

    An empty result means the file says nothing, which is not an error: a
    project may keep one for the sake of the tags alone.
    """
    try:
        data = tomli.loads(path.read_text(encoding='utf-8'))
    except OSError as exc:
        raise UsageError(f'cannot read {path}: {exc.strerror}') from exc
    except tomli.TOMLDecodeError as exc:
        raise UsageError(f'{path} is not valid TOML: {exc}') from exc

    try:
        parsed = Settings.model_validate(data)
    except pydantic.ValidationError as exc:
        raise UsageError(_prose(path, exc, data)) from None

    settings = parsed.as_arguments(only_set=True)
    root = path.parent
    for name, value in settings.items():
        field = Settings.model_fields[_field_of(name)]
        for mark in field.metadata:
            if isinstance(mark, AgainstConfigFile):
                settings[name] = _against(root, value, mark.only_if_file)
    return settings


def _field_of(setting: str) -> str:
    """The field holding `setting`, which is its own name but for `json`."""
    return JSON_FIELD if setting == JSON_SETTING else setting


def _setting_of(field: str) -> str:
    """The name the user writes for `field`, dashes and all."""
    return _dashed(JSON_SETTING if field == JSON_FIELD else field)


def _as_written(name: str, data: dict[str, Any]) -> str:
    """`name` spelled as the file spells it.

    A setting may be written with either dashes or underscores, and pydantic
    reports whichever is the field's alias.  A message about someone's file
    should quote their file, not our spelling of it.
    """
    setting = _setting_of(name)
    if setting in data:
        return setting
    underscored = setting.replace('-', '_')
    return underscored if underscored in data else setting


#: What a value of the wrong type is, said as the user would say it.  pydantic
#: reports 'Input should be a valid boolean', which is true but is not about
#: their file; this is.  A type missing from here falls back to pydantic's own
#: wording, which is a signal that a row is needed rather than a crash.
_WRONG_TYPE = {
    'bool_type': 'must be true or false',
    'bool_parsing': 'must be true or false',
    'string_type': 'must be a string',
    'list_type': 'must be a list of strings',
    'dict_type': 'must be a table',
    'model_type': 'must be a table',
    'model_attributes_type': 'must be a table',
    'enum': 'must be one of ' + ', '.join(text.value for text in TAG_TEXTS),
}


def _prose(
    path: pathlib.Path, exc: pydantic.ValidationError, data: dict[str, Any]
) -> str:
    """The first thing wrong with the file, said the way cmake2md says things.

    Only the first: a file with two mistakes in it is fixed one at a time, and
    a wall of them buries the one being looked at.
    """
    error = exc.errors()[0]
    kind = error['type']
    loc = error['loc']
    # A [tags] entry is named as the file names it, so that the message points
    # at the table the author would go and look at.
    in_tags = bool(loc) and loc[0] == 'tags'
    where = f'{path}: [tags]' if in_tags else f'{path}:'
    if in_tags:
        loc = loc[1:]
    at = '.'.join(
        str(part) if in_tags else _as_written(str(part), data) for part in loc
    )

    if kind == 'extra_forbidden':
        if loc[:-1]:
            known = ', '.join(sorted(TagSettings.model_fields))
            owner = '.'.join(str(part) for part in loc[:-1])
            return (
                f'{where} {owner} has no setting called {loc[-1]}; a tag takes: {known}'
            )
        known = ', '.join(sorted(_setting_of(name) for name in Settings.model_fields))
        return f'{where} has no setting called {loc[-1]}; the settings are: {known}'

    # Ours raise ValueError, whose wording is already the final one; pydantic
    # prefixes it, and nothing else here should be spelled twice.
    if kind == 'value_error':
        return f'{where} {error["msg"].removeprefix("Value error, ")}'

    what = _WRONG_TYPE.get(kind)
    if what is None:
        return f'{where} {at}: {error["msg"]}' if at else f'{where} {error["msg"]}'
    return f'{where} {at} {what}' if at else f'{where} {what}'


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


def _capitalized(name: str) -> str:
    """Uppercase the first letter of `name`, leaving the rest as written.

    str.capitalize() would also lowercase the rest, turning a tag such as
    @myTag into the label 'Mytag:' rather than 'MyTag:'.
    """
    return name[:1].upper() + name[1:]
