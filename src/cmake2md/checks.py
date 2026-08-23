"""Cross-checks between what a symbol documents and what its code accepts.

Documentation that merely restates the code drifts away from it; these checks
are what turns the restatement into something the build can verify.  They stay
silent about anything :mod:`cmake2md.signature` could not read, so a warning
here always means a real disagreement.

The same idea applies to an ``@example``: the sample is CMake, so it can be
parsed, which is as close to rustdoc's doc tests as a build language gets.
"""

from collections.abc import Collection

from . import parse
from . import rendering
from .doc_parser import DocComment
from .doc_parser import DocWarning
from .doc_parser import ParamKind
from .doc_parser import TAG_SPECS
from .doc_parser import TagTarget

#: Fence languages whose body is CMake and so worth parsing.
_CMAKE_FENCES = frozenset({'', 'cmake'})


def tag(kind: ParamKind) -> str:
    """The kind as the author would have written it."""
    return '@' + kind.value


def does(kind: ParamKind) -> str:
    """What a definition does with a parameter of `kind`."""
    return 'sets' if kind == ParamKind.OutVar else 'takes'


def does_not(kind: ParamKind) -> str:
    return 'does not set' if kind == ParamKind.OutVar else 'does not accept'


def check(
    item: parse.Documented,
    doc: DocComment,
    groups: Collection[str] = (),
) -> list[DocWarning]:
    """Report where `doc` disagrees with the code it documents.

    A symbol with no doc comment at all is left alone: it is not drifting, it
    is simply undocumented, which is a separate question (--require-docs).
    One documented with only a @brief and no parameters at all is still
    checked against its own code: a keyword the body accepts is missing from
    the comment either way, whether or not another keyword happens to be
    documented already.
    """
    warnings = _broken_examples(doc)
    warnings += _ingroup_names_no_group(doc, groups)
    warnings += _misplaced_block_only_tags(item, doc)
    if isinstance(item, parse.Symbol) and _has_comment(item):
        warnings += _duplicate_params(doc)
        warnings += _params_the_code_denies(item, doc)
        warnings += _params_the_comment_omits(item, doc)
    return warnings


def _has_comment(item: parse.Documented) -> bool:
    return any(line.strip() for line in item.comments)


def cmake_snippets(text: str) -> list[str]:
    """The parts of `text` that claim to be CMake.

    An @example is CMake unless it says otherwise, which it does by fencing
    the sample and naming another language.
    """
    fences = rendering.FENCE_RE.findall(text)
    if not fences:
        return [text]
    return [body for language, body in fences if language in _CMAKE_FENCES]


def _ingroup_names_no_group(
    doc: DocComment, groups: Collection[str]
) -> list[DocWarning]:
    """Report an @ingroup naming a group that no @defgroup defines.

    Only checked once some group exists: a project that never writes
    @defgroup is using @ingroup as a bare label, which is how cmake2md worked
    before groups had titles, and is nothing to complain about.
    """
    if groups and doc.group is not None and doc.group not in groups:
        return [
            DocWarning(
                f'@ingroup {doc.group} names a group that no @defgroup defines',
                doc.group_line,
            )
        ]
    return []


def _misplaced_block_only_tags(
    item: parse.Documented, doc: DocComment
) -> list[DocWarning]:
    """Report a tag marked `block_only` written above anything but a Block.

    @defgroup and @file each attach to the comment block as a whole rather
    than to whatever the block happens to sit above; on a Symbol, Command or
    Variable they would define or document nothing, and silently.
    """
    if isinstance(item, parse.Block):
        return []

    warnings = []
    for name, spec in TAG_SPECS.items():
        if not spec.block_only:
            continue
        if spec.target is TagTarget.Section:
            for section in doc.of_kind(name):
                warnings.append(
                    DocWarning(
                        f'@{name} {section.name} in the documentation of '
                        f'{item.name} defines nothing; a group is defined in '
                        'a comment block of its own',
                        section.line,
                    )
                )
        elif spec.target is TagTarget.DocField and getattr(doc, spec.field):
            warnings.append(
                DocWarning(
                    f'@{name} in the documentation of {item.name} documents '
                    'nothing; a file is documented by a comment block of its '
                    'own',
                    line=0,
                )
            )
    return warnings


def _broken_examples(doc: DocComment) -> list[DocWarning]:
    warnings = []
    for section in doc.of_kind('example'):
        for snippet in cmake_snippets(section.text):
            if parse.PARSER.parse(snippet.encode()).root_node.has_error:
                warnings.append(
                    DocWarning(
                        'the @example does not parse as CMake; put prose or '
                        'another language in a fenced code block',
                        section.line,
                    )
                )
    return warnings


def _duplicate_params(doc: DocComment) -> list[DocWarning]:
    warnings = []
    seen: set[str] = set()
    for param in doc.all_params():
        if param.name in seen:
            warnings.append(DocWarning(f'{param.name} is documented twice', param.line))
        seen.add(param.name)
    return warnings


def _params_the_code_denies(symbol: parse.Symbol, doc: DocComment) -> list[DocWarning]:
    """Documented parameters the definition does not take, or takes otherwise."""
    warnings = []
    for param in doc.all_params():
        accepted = symbol.signature.accepts[param.kind]
        if accepted is None or param.name in accepted:
            continue

        declared = symbol.signature.declares(param.name)
        if declared is None:
            message = (
                f'{param.name} is documented as {tag(param.kind)} but '
                f'{symbol.name} {does_not(param.kind)} it'
            )
        else:
            message = (
                f'{param.name} is documented as {tag(param.kind)} but '
                f'{symbol.name} {does(declared)} it as {tag(declared)}'
            )
        warnings.append(DocWarning(message, param.line))
    return warnings


def _params_the_comment_omits(
    symbol: parse.Symbol, doc: DocComment
) -> list[DocWarning]:
    documented = {param.name for param in doc.all_params()}
    warnings = []
    for kind, accepted in symbol.signature.accepts.items():
        for name in accepted or []:
            if name not in documented:
                warnings.append(
                    DocWarning(
                        f'{symbol.name} {does(kind)} {name} but it is not '
                        f'documented; add {tag(kind)} {name}',
                        # The tag is missing, so the best line to point at is
                        # the definition's own; location_at() resolves 0 to it.
                        line=0,
                    )
                )
    return warnings
