"""Finding and filtering the CMake source files to read."""

import fnmatch
import glob
import pathlib
from collections.abc import Sequence

from .errors import UsageError

#: What a directory given as CMAKE_FILE is searched for.
SOURCE_GLOBS = ('CMakeLists.txt', '*.cmake')
#: File listing extra --exclude patterns, one per line, '#' starting a comment.
IGNORE_FILE = '.cmake2mdignore'


def _read_text(path: pathlib.Path) -> str:
    try:
        return path.read_text(encoding='utf-8')
    except OSError as exc:
        raise UsageError(f'cannot read {path}: {exc.strerror}') from exc


def read_ignore_file(directory: pathlib.Path) -> list[str]:
    """The patterns in `directory`/.cmake2mdignore, if there is one."""
    path = directory / IGNORE_FILE
    if not path.is_file():
        return []
    return [
        line.strip()
        for line in _read_text(path).splitlines()
        if line.strip() and not line.lstrip().startswith('#')
    ]


def is_excluded(path: pathlib.Path, patterns: Sequence[str]) -> bool:
    """Whether `path` matches a pattern, as a whole path or as a name.

    Both are tried because '*/tests/*' and 'test_*.cmake' are both natural
    ways to say what to leave out.
    """
    text = path.as_posix()
    return any(
        fnmatch.fnmatch(text, pattern) or fnmatch.fnmatch(path.name, pattern)
        for pattern in patterns
    )


def collect_sources(
    paths: Sequence[str], exclude: Sequence[str] = ()
) -> list[pathlib.Path]:
    """Expand `paths` into the CMake files to read.

    A directory is searched, and a pattern expanded, because the shells that
    would otherwise do it (and Windows' do not) are not always in the picture:
    cmake2md is typically run from a build system or a CI step.

    A file reached twice — a directory and a glob both matching it, or the
    same file named twice on the command line — is read once: reading it
    again would document every symbol in it twice over.
    """
    found: list[pathlib.Path] = []
    seen: set[pathlib.Path] = set()
    for path in paths:
        candidate = pathlib.Path(path)
        if candidate.is_dir():
            matches = sorted(
                match
                for pattern in SOURCE_GLOBS
                for match in candidate.rglob(pattern)
                if not any(part.startswith('.') for part in match.parts)
            )
        elif candidate.exists():
            matches = [candidate]
        else:
            matches = sorted(pathlib.Path(m) for m in glob.glob(path, recursive=True))
        if not matches:
            raise UsageError(f'no CMake sources found at {path}')
        for match in matches:
            if is_excluded(match, exclude):
                continue
            resolved = match.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            found.append(match)
    return found
