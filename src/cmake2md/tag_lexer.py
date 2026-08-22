"""Tokenizer for the doxygen-like ``@tag`` markup used in CMake comments.

``tokenize()`` turns a block of comment lines into a flat stream of literal
text chunks and :class:`Tag` markers.  It knows nothing about which tags
exist; that is :mod:`cmake2md.doc_parser`'s job.
"""

import dataclasses
import re
from typing import Sequence

# A tag name is an identifier: this deliberately includes '_' and digits so
# that '@param_x' lexes as one tag rather than '@param' followed by '_x'.
TAG_RE = re.compile(r'@([A-Za-z_][A-Za-z0-9_]*)')


@dataclasses.dataclass(frozen=True)
class Tag:
    name: str
    # 1-based line number within the comment block, for diagnostics only.
    line: int = dataclasses.field(default=0, compare=False)


def tokenize(lines: Sequence[str]) -> list[Tag | str]:
    """Split comment lines into literal chunks and tags.

    An '@' only starts a tag at the beginning of the text or after
    whitespace, so 'user@example.com' stays literal.  '@@' is an escape for
    a literal '@'.
    """
    text = '\n'.join(lines)
    tokens: list[Tag | str] = []
    buf: list[str] = []
    pos = 0

    def flush() -> None:
        literal = ''.join(buf)
        buf.clear()
        if literal:
            tokens.append(literal)

    while pos < len(text):
        at = text.find('@', pos)
        if at == -1:
            buf.append(text[pos:])
            break

        buf.append(text[pos:at])
        pos = at

        if text.startswith('@@', pos):
            buf.append('@')
            pos += 2
            continue

        at_word_start = at == 0 or text[at - 1].isspace()
        m = TAG_RE.match(text, pos) if at_word_start else None
        if m is None:
            buf.append('@')
            pos += 1
            continue

        flush()
        tokens.append(Tag(name=m.group(1), line=text.count('\n', 0, pos) + 1))
        pos = m.end()

    flush()
    return tokens
