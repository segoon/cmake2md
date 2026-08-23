"""The ``cmake2doc.toml`` a project keeps beside its CMake code.

A CI step that renders three templates needs six paired arguments to say so,
and they have to be kept in step across a Makefile, a workflow file and a
pre-commit hook.  A config file says it once.

The settings are the whole file: it is cmake2doc's own, so it needs no table
to say whose settings these are.  A relative path in it is relative to the
file, which is the only reading that survives being run from a subdirectory.

`_RawSettings` is the single declaration of what the file may hold: the
settings, their types, and what each is worth when unsaid.  `Settings` is
the resolved view over it that `cli` actually uses, and reads its defaults
from the same place, so the two cannot drift apart.
"""

import dataclasses
import pathlib
from typing import Annotated

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
DEFAULT_FILE = 'cmake2doc.toml'
#: What stops that search: past a repository, the file would not be this
#: project's own any more.
ROOT_MARKERS = ('.git',)

#: A custom tag holds text; a flag or a label would have nowhere on the parsed
#: comment to be stored, so those stay built-in.
TAG_TEXTS = (doc_parser.TagText.Paragraph, doc_parser.TagText.Block)

#: The one setting whose field cannot be named after it: see `_RawSettings.json_`.
JSON_FIELD = 'json_'
JSON_SETTING = 'json'


def _check_tag_name(name: str) -> str:
    """A key of the [tags] table: a name a tag can have, and not one taken."""
    # A tag the lexer would not read as one whole tag could never be written.
    if tag_lexer.TAG_RE.fullmatch('@' + name) is None:
        raise ValueError(
            f'{name} is not a name a tag can have: a tag is written '
            '@ and a letter or _, then letters, digits and _'
        )
    if name in doc_parser.TAG_SPECS:
        raise ValueError(f'@{name} is already a tag of cmake2doc')
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

    # No dashed aliases here, unlike `_RawSettings`: a tag's settings are not
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


class _RawSettings(pydantic.BaseModel):
    """What cmake2doc.toml literally says, before any path in it is resolved.

    Anything else in it is a mistake worth pointing out rather than ignoring,
    which is what `extra='forbid'` says.  Every setting is also a long option,
    and is spelled here as that option is, so `require-docs` and
    `require_docs` both name this field.
    """

    model_config = pydantic.ConfigDict(
        extra='forbid', alias_generator=_dashed, populate_by_name=True
    )

    template: StrList = []
    output: StrList = []
    template_dir: StrList = []
    path: StrList = []
    #: Not a path but a glob matched against one, so it is left as written.
    exclude: StrList = []
    #: Trailing underscore because a field called `json` shadows a method of
    #: pydantic's own base class, which it warns about; `JSON_SETTING` puts
    #: the name back before anything outside this module sees it.
    json_: Annotated[
        pydantic.StrictStr | None, pydantic.Field(validation_alias='json')
    ] = None
    inject: pydantic.StrictBool = False
    check: pydantic.StrictBool = False
    require_docs: pydantic.StrictBool = False
    strict: pydantic.StrictBool = True
    tags: dict[TagName, TagSettings] = {}


@dataclasses.dataclass(frozen=True)
class Settings:
    """A cmake2doc.toml file's settings, with every path in it resolved
    against the file's own directory — the only reading that survives being
    run from a subdirectory.  Built once, by `resolve()`, from a
    `_RawSettings` — which is only what pydantic validated, paths exactly as
    the file wrote them — and holds no reference back to it.
    """

    template: list[str]
    output: list[str]
    template_dir: list[str]
    path: list[str]
    exclude: list[str]
    json: str | None
    inject: bool
    check: bool
    require_docs: bool
    strict: bool
    tags: dict[str, doc_parser.TagSpec]

    @classmethod
    def defaults(cls) -> 'Settings':
        """cmake2doc's own defaults: nothing read from a file, so nothing to
        resolve — `root` is never touched, since every default is empty or
        None.
        """
        return cls.resolve(_RawSettings(), root=pathlib.Path())

    @classmethod
    def resolve(cls, raw: _RawSettings, root: pathlib.Path) -> 'Settings':
        """Read `raw` the way `root`, the config file's own directory, makes
        every path in it read the same regardless of where cmake2doc was run
        from.
        """
        return cls(
            # only_if_file=True: a spec that isn't an existing file names a
            # built-in template, and must be left as written.
            template=[_against(root, item, only_if_file=True) for item in raw.template],
            output=[_against(root, item) for item in raw.output],
            template_dir=[_against(root, item) for item in raw.template_dir],
            path=[_against(root, item) for item in raw.path],
            exclude=raw.exclude,
            # A plain dataclass, not a BaseModel, so `json` needs no alias trick.
            json=None if raw.json_ is None else _against(root, raw.json_),
            inject=raw.inject,
            check=raw.check,
            require_docs=raw.require_docs,
            strict=raw.strict,
            tags={name: tag.to_spec(name) for name, tag in raw.tags.items()},
        )


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


def _read_raw(path: pathlib.Path) -> _RawSettings:
    """Validate `path` as a cmake2doc.toml, or say what's wrong with it."""
    try:
        data: dict[str, object] = tomli.loads(path.read_text(encoding='utf-8'))
    except OSError as exc:
        raise UsageError(f'cannot read {path}: {exc.strerror}') from exc
    except tomli.TOMLDecodeError as exc:
        raise UsageError(f'{path} is not valid TOML: {exc}') from exc

    try:
        return _RawSettings.model_validate(data)
    except pydantic.ValidationError as exc:
        raise UsageError(_prose(path, exc, data)) from None


def resolve(path: pathlib.Path | None) -> Settings:
    """`path`'s settings, every field resolved — the file's own value where
    it named one, cmake2doc's own default otherwise — or cmake2doc's own
    defaults outright when there is no file at all.
    """
    if path is None:
        return Settings.defaults()
    return Settings.resolve(_read_raw(path), root=path.parent)


def _setting_of(field: str) -> str:
    """The name the user writes for `field`, dashes and all."""
    return _dashed(JSON_SETTING if field == JSON_FIELD else field)


def _as_written(name: str, data: dict[str, object]) -> str:
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
    path: pathlib.Path, exc: pydantic.ValidationError, data: dict[str, object]
) -> str:
    """The first thing wrong with the file, said the way cmake2doc says things.

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
        known = ', '.join(
            sorted(_setting_of(name) for name in _RawSettings.model_fields)
        )
        return f'{where} has no setting called {loc[-1]}; the settings are: {known}'

    # Ours raise ValueError, whose wording is already the final one; pydantic
    # prefixes it, and nothing else here should be spelled twice.
    if kind == 'value_error':
        return f'{where} {error["msg"].removeprefix("Value error, ")}'

    what = _WRONG_TYPE.get(kind)
    if what is None:
        return f'{where} {at}: {error["msg"]}' if at else f'{where} {error["msg"]}'
    return f'{where} {at} {what}' if at else f'{where} {what}'


def _against(root: pathlib.Path, value: str, only_if_file: bool = False) -> str:
    """Read a path the config file gives as relative to the file itself.

    Anything else would depend on where cmake2doc happened to be run from,
    which is exactly what a config file at the project root is there to stop
    mattering.  `STDOUT` is not a path at all, and must be left alone:
    resolving it against a directory would create a file called `-` instead
    of writing to standard output.  Called once per item of a list setting,
    and once for a lone one, by `Settings.resolve()`.
    """
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
