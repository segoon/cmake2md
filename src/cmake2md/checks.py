"""Cross-checks between what a symbol documents and what its code accepts.

Documentation that merely restates the code drifts away from it; these checks
are what turns the restatement into something the build can verify.  They stay
silent about anything :mod:`cmake2md.signature` could not read, so a warning
here always means a real disagreement.
"""

from . import parse
from .doc_parser import DocComment
from .doc_parser import DocWarning
from .doc_parser import ParamKind


def tag(kind: ParamKind) -> str:
    """The kind as the author would have written it."""
    return '@' + kind.value


def does(kind: ParamKind) -> str:
    """What a definition does with a parameter of `kind`."""
    return 'sets' if kind == ParamKind.OutVar else 'takes'


def does_not(kind: ParamKind) -> str:
    return 'does not set' if kind == ParamKind.OutVar else 'does not accept'


def check(item: parse.Documented, doc: DocComment) -> list[DocWarning]:
    """Report where `doc` disagrees with the code of `item`.

    An item that is not documented at all is left alone: it is not drifting,
    it is simply undocumented, which is a separate question.
    """
    if not isinstance(item, parse.Symbol) or not doc.all_params():
        return []

    warnings = _duplicate_params(doc)
    warnings += _params_the_code_denies(item, doc)
    warnings += _params_the_comment_omits(item, doc)
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
