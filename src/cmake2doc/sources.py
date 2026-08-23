"""Finding and filtering the CMake source files to read."""

import fnmatch
import glob
import pathlib
from collections.abc import Sequence

from .errors import UsageError

#: What a directory given as CMAKE_FILE is searched for.
SOURCE_GLOBS = ('CMakeLists.txt', '*.cmake')
#: File listing extra --exclude patterns, one per line, '#' starting a comment.
IGNORE_FILE = '.cmake2docignore'


def _read_text(path: pathlib.Path) -> str:
    try:
        return path.read_text(encoding='utf-8')
    except OSError as exc:
        raise UsageError(f'cannot read {path}: {exc.strerror}') from exc


def read_ignore_file(directory: pathlib.Path) -> list[str]:
    """The patterns in `directory`/.cmake2docignore, if there is one."""
    path = directory / IGNORE_FILE
    if not path.is_file():
        return []
    patterns = []
    for raw in _read_text(path).splitlines():
        line = raw.strip()
        if line and not line.startswith('#'):
            patterns.append(line)
    return patterns


def is_excluded(path: pathlib.Path, patterns: Sequence[str]) -> bool:
    """Whether `path` matches a pattern, as a whole path or as a name.

    Both are tried because '*/tests/*' and 'test_*.cmake' are both natural
    ways to say what to leave out.
    """
    text = path.as_posix()
    for pattern in patterns:
        if fnmatch.fnmatch(text, pattern) or fnmatch.fnmatch(path.name, pattern):
            return True
    return False


def collect_sources(
    paths: Sequence[str], exclude: Sequence[str] = ()
) -> list[pathlib.Path]:
    """Expand `paths` into the CMake files to read.

    A directory is searched, and a pattern expanded, because the shells that
    would otherwise do it (and Windows' do not) are not always in the picture:
    cmake2doc is typically run from a build system or a CI step.

    A file reached twice — a directory and a glob both matching it, or the
    same file named twice on the command line — is read once: reading it
    again would document every symbol in it twice over.
    """
    found: list[pathlib.Path] = []
    for path in paths:
        candidate = pathlib.Path(path)
        if candidate.is_dir():
            matches = [
                match
                for pattern in SOURCE_GLOBS
                for match in candidate.rglob(pattern)
                if not any(part.startswith('.') for part in match.parts)
            ]
        elif candidate.exists():
            matches = [candidate]
        else:
            matches = [pathlib.Path(m) for m in glob.glob(path, recursive=True)]
        if not matches:
            raise UsageError(f'no CMake sources found at {path}')
        found += [match for match in matches if not is_excluded(match, exclude)]
    return sorted(set(found))
