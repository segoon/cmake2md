"""The ``[tool.cmake2md]`` table of a ``pyproject.toml``.

A CI step that renders three templates needs six paired arguments to say so,
and they have to be kept in step across a Makefile, a workflow file and a
pre-commit hook.  A config file says it once.

``tomli`` reads it on every version.  The standard library grew the same
parser as ``tomllib`` in 3.11, but reaching for whichever of the two is
present would mean a version check and a branch that only the oldest
interpreter in the test matrix ever runs — a poor trade against one small
dependency with nothing under it.
"""

import pathlib
from typing import Any

import tomli

from .errors import UsageError

#: Where the settings live, and the file they live in by default.
DEFAULT_FILE = 'pyproject.toml'
TABLE = 'tool.cmake2md'

#: Settings the file may carry, and whether each is a list.  Anything else in
#: the table is a mistake worth pointing out rather than ignoring.
KEYS = {
    'template': True,
    'output': True,
    'template_dir': True,
    'path': True,
    'exclude': True,
    'json': False,
    'inject': False,
    'strict': False,
    'check': False,
    'require_docs': False,
}


def load(path: pathlib.Path) -> dict[str, Any]:
    """Read the [tool.cmake2md] table of `path`.

    An empty result means the file has nothing to say about cmake2md, which
    is not an error: a project may keep a pyproject.toml for other reasons.
    """
    try:
        data = tomli.loads(path.read_text(encoding='utf-8'))
    except OSError as exc:
        raise UsageError(f'cannot read {path}: {exc.strerror}') from exc
    except tomli.TOMLDecodeError as exc:
        raise UsageError(f'{path} is not valid TOML: {exc}') from exc

    table = data.get('tool', {}).get('cmake2md', {})
    if not isinstance(table, dict):
        raise UsageError(f'{path}: [{TABLE}] must be a table')

    settings = {}
    for key, value in table.items():
        name = key.replace('-', '_')
        if name not in KEYS:
            known = ', '.join(sorted(KEYS))
            raise UsageError(
                f'{path}: [{TABLE}] has no setting called {key}; '
                f'the settings are: {known}'
            )
        settings[name] = _as_list(path, key, value) if KEYS[name] else value
    return settings


def _as_list(path: pathlib.Path, key: str, value: Any) -> list[str]:
    """Accept a lone string where a list is expected, as TOML users expect."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return list(value)
    raise UsageError(f'{path}: [{TABLE}] {key} must be a string or a list of them')
