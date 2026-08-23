"""Writing (or, under --check, comparing) generated output files."""

import difflib
import pathlib
import sys

from . import rendering
from .errors import UsageError


def _read_text(path: pathlib.Path) -> str:
    try:
        return path.read_text(encoding='utf-8')
    except OSError as exc:
        raise UsageError(f'cannot read {path}: {exc.strerror}') from exc


def write_output(
    path: pathlib.Path, content: str, check: bool, inject: bool = False
) -> bool:
    """Write `content`, or in check mode report whether it is up to date."""
    if inject:
        if not path.exists():
            raise UsageError(
                f'--inject needs {path} to exist already, with the markers to '
                'inject between'
            )
        content = rendering.inject(_read_text(path), content, str(path))

    if check:
        if not path.exists():
            print(f'{path}: would be created', file=sys.stderr)
            return False
        current = _read_text(path)
        if current == content:
            return True
        print(f'{path}: out of date', file=sys.stderr)
        # The diff is what makes the failure actionable in CI, where nobody
        # can re-run the generator to see what changed.
        sys.stderr.writelines(
            difflib.unified_diff(
                current.splitlines(keepends=True),
                content.splitlines(keepends=True),
                fromfile=f'{path} (on disk)',
                tofile=f'{path} (generated)',
            )
        )
        return False

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        # Explicit newline: on Windows the default would write CRLF, so
        # generated documentation would differ per platform and --check
        # would never settle.
        path.write_text(content, encoding='utf-8', newline='\n')
    except OSError as exc:
        raise UsageError(f'cannot write {path}: {exc.strerror}') from exc
    return True


def list_templates() -> int:
    for name in sorted(rendering.builtin_loader().list_templates()):
        print(name)
    return 0
