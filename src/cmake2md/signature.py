"""What a function() or macro() accepts, as told by its own code.

CMake states a definition's interface twice: once in the doc comment and once
in the code, as the named arguments of ``function()`` and the keyword lists of
``cmake_parse_arguments()``.  Reading the second one lets :mod:`cmake2md.checks`
report when the two have drifted apart, and lets a template render what the
author did not spell out.

The code often does not state a thing, though — a macro reaching for ``ARGV0``,
a keyword list built up in a variable — and a guess there would turn into a
wrong diagnostic.  So each kind is either known exactly or not at all, and an
unknown kind is nobody's business but the author's.
"""

import dataclasses

from .doc_parser import ParamKind


@dataclasses.dataclass(frozen=True)
class Signature:
    """The parameter names a definition accepts, by kind.

    A ``None`` value means the code does not say; an empty list means it says
    there are none.  Every kind is always present as a key, so a template can
    ask about one without checking first.
    """

    accepts: dict[ParamKind, list[str] | None]

    def declares(self, name: str) -> ParamKind | None:
        """The kind `name` is declared as, or None if it is not declared."""
        return next(
            (kind for kind, names in self.accepts.items() if names and name in names),
            None,
        )


def unknown() -> Signature:
    """A signature that says nothing, for code cmake2md cannot read."""
    return Signature(accepts={kind: None for kind in ParamKind})
