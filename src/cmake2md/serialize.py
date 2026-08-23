"""The parsed model as JSON, for the tools that are not Jinja templates.

Templates are the usual way out of cmake2md, but a documentation site
generator, a linter or a diff tool wants the model itself.  This is that
model, written as it is handed to a template, with a version on it so a
consumer can tell when it has changed underneath.
"""

import dataclasses
import json

from . import entries

#: Bumped when a field disappears or changes meaning.  A field being *added*
#: does not bump it, so a consumer must ignore the ones it does not know.
SCHEMA_VERSION = 1


def dump(context: entries.Context) -> str:
    payload = {
        'schema_version': SCHEMA_VERSION,
        'symbols': [dataclasses.asdict(item) for item in context.symbols],
        'variables': [dataclasses.asdict(item) for item in context.variables],
        'commands': [dataclasses.asdict(item) for item in context.commands],
        'groups': [dataclasses.asdict(item) for item in context.groups],
        'files': [dataclasses.asdict(item) for item in context.files],
    }
    return json.dumps(payload, indent=2) + '\n'
