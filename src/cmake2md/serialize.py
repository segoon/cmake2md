"""The parsed model as JSON, for the tools that are not Jinja templates.

Templates are the usual way out of cmake2md, but a documentation site
generator, a linter or a diff tool wants the model itself.  This is that
model, written as it is handed to a template, with a version on it so a
consumer can tell when it has changed underneath.
"""

import dataclasses
import json
from typing import Any

#: Bumped when a field disappears or changes meaning.  A field being *added*
#: does not bump it, so a consumer must ignore the ones it does not know.
SCHEMA_VERSION = 1


def as_data(item: dict[str, Any]) -> dict[str, Any]:
    """A context entry with its parsed comment flattened into plain data."""
    out = dict(item)
    doc = out.get('doc')
    if dataclasses.is_dataclass(doc) and not isinstance(doc, type):
        out['doc'] = dataclasses.asdict(doc)
    return out


def dump(context: dict[str, list[dict[str, Any]]]) -> str:
    payload: dict[str, Any] = {'schema_version': SCHEMA_VERSION}
    for key, entries in context.items():
        payload[key] = [as_data(entry) for entry in entries]
    return json.dumps(payload, indent=2) + '\n'
