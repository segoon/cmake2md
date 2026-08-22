"""Command line entry point."""

import argparse
import dataclasses
import difflib
import fnmatch
import glob
import pathlib
import sys
from collections.abc import Sequence
from typing import Any

import jinja2

from . import __version__
from . import checks
from . import doc_parser
from . import parse
from . import rendering
from . import serialize
from . import tag_lexer
from .errors import Cmake2mdError
from .errors import ParseError
from .errors import UsageError

#: The --output value that means "write to stdout" instead of to a file.
STDOUT = '-'
#: What a directory given as CMAKE_FILE is searched for.
SOURCE_GLOBS = ('CMakeLists.txt', '*.cmake')
#: File listing extra --exclude patterns, one per line, '#' starting a comment.
IGNORE_FILE = '.cmake2mdignore'


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog='cmake2md',
        description=(
            'Generate documentation from CMake sources by extracting '
            'doxygen-like comments and rendering them with Jinja templates.'
        ),
    )
    parser.add_argument(
        '--version',
        action='version',
        version=f'cmake2md {__version__}',
        help='Show the version and exit.',
    )
    parser.add_argument(
        '-t',
        '--template',
        action='append',
        default=[],
        metavar='TEMPLATE',
        help=(
            'Jinja template to render; either a path or the name of a '
            'built-in template. Repeatable, paired with --output in order.'
        ),
    )
    parser.add_argument(
        '-o',
        '--output',
        action='append',
        default=[],
        metavar='OUTPUT',
        help='Where to write the corresponding --template. Repeatable.',
    )
    parser.add_argument(
        '-I',
        '--template-dir',
        action='append',
        default=[],
        metavar='DIR',
        help='Additional directory to search for templates. Repeatable.',
    )
    parser.add_argument(
        '--inject',
        action='store_true',
        help=(
            'Write into an existing --output file, between its '
            f'{rendering.INJECT_BEGIN} and {rendering.INJECT_END} lines, '
            'instead of replacing the whole file.'
        ),
    )
    parser.add_argument(
        '--json',
        metavar='OUTPUT',
        help=(
            'Also write the parsed model as JSON, for tools that are not '
            'templates. Use - for stdout.'
        ),
    )
    parser.add_argument(
        '--exclude',
        action='append',
        default=[],
        metavar='PATTERN',
        help=(
            'Skip source files matching this glob, against either the whole '
            'path or the file name. Repeatable.'
        ),
    )
    parser.add_argument(
        '--require-docs',
        action='store_true',
        help=(
            'Exit non-zero if a public function() or macro() carries no doc '
            'comment. A name starting with _ is private and is not required '
            'to have one.'
        ),
    )
    parser.add_argument(
        '--strict',
        action='store_true',
        help=(
            'Treat documentation warnings as errors: a doubtful @tag, and a '
            'doc comment that disagrees with the code it documents.'
        ),
    )
    parser.add_argument(
        '--check',
        action='store_true',
        help=(
            'Do not write anything; exit non-zero if any output is missing '
            'or differs from what is already on disk.'
        ),
    )
    parser.add_argument(
        '--list-templates',
        action='store_true',
        help='List the built-in template names and exit.',
    )
    parser.add_argument(
        'path',
        nargs='*',
        metavar='CMAKE_FILE',
        help=(
            'CMake sources to read: files, directories to search for '
            'CMakeLists.txt and *.cmake, or glob patterns.'
        ),
    )
    return parser


def validate_args(args: argparse.Namespace) -> list[tuple[str, str]]:
    if not args.template:
        raise UsageError('no --template given, nothing to render')
    if not args.path:
        raise UsageError('no CMAKE_FILE given, nothing to read')
    if len(args.template) != len(args.output):
        if not args.output and any(':' in t for t in args.template):
            raise UsageError(
                'the TEMPLATE:OUTPUT form is no longer supported; '
                'use --template TEMPLATE --output OUTPUT instead'
            )
        raise UsageError(
            f'got {len(args.template)} --template and {len(args.output)} '
            '--output arguments; each template needs exactly one output'
        )
    if args.check and (STDOUT in args.output or args.json == STDOUT):
        raise UsageError(f'--output {STDOUT} writes nothing to check')

    # Two templates rendering into one file: one of the two results would be
    # silently thrown away, which can only be a mistake.
    seen: dict[str, str] = {}
    for template, output in zip(args.template, args.output, strict=True):
        if output == STDOUT:
            continue
        key = str(pathlib.Path(output).resolve())
        if key in seen:
            raise UsageError(
                f'--output {output} is given twice, for {seen[key]} and '
                f'{template}; each template needs its own output'
            )
        seen[key] = template

    # The lengths are equal by the check above.
    return list(zip(args.template, args.output, strict=True))


def read_ignore_file(directory: pathlib.Path) -> list[str]:
    """The patterns in `directory`/.cmake2mdignore, if there is one."""
    path = directory / IGNORE_FILE
    if not path.is_file():
        return []
    return [
        line.strip()
        for line in path.read_text(encoding='utf-8').splitlines()
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
    """
    found: list[pathlib.Path] = []
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
        found += [m for m in matches if not is_excluded(m, exclude)]
    return found


def report(
    item: parse.Documented,
    warnings: Sequence[doc_parser.DocWarning],
    strict: bool,
) -> None:
    """Print each warning, or fail on the first one under --strict."""
    for warning in warnings:
        location = item.location_at(warning.line)
        if strict:
            raise ParseError(warning.message, location)
        print(f'{location}: warning: {warning.message}', file=sys.stderr)


def enrich(
    item: parse.Documented,
    function_template: jinja2.Template | None,
    strict: bool,
    groups: frozenset[str] = frozenset(),
) -> dict[str, Any]:
    """Attach the parsed doc comment and a rendered form to `item`."""
    try:
        doc = doc_parser.parse(
            tag_lexer.tokenize(item.comments),
            strict=strict,
            first_line=item.comments_line or item.line,
        )
    except ParseError as exc:
        raise exc.at(item.location_at(exc.line)) from None

    report(item, doc.warnings + checks.check(item, doc, groups), strict)

    res = dataclasses.asdict(item)
    res['doc'] = doc
    res['group'] = doc.group
    res['location'] = item.location
    if function_template is not None:
        res['pretty'] = function_template.render({'symbol': res}).strip()
    else:
        # A command call has no signature of its own to render, so there is
        # nothing for the function template to do with it.
        res['pretty'] = doc.description
    return res


def report_undocumented(symbols: Sequence[dict[str, Any]]) -> bool:
    """Report every public symbol that carries no doc comment.

    A leading underscore is CMake's way of saying a function is private, and
    @internal says it outright; neither is required to be documented.
    """
    ok = True
    for symbol in symbols:
        if symbol['name'].startswith('_') or symbol['doc'].internal:
            continue
        if any(line.strip() for line in symbol['comments']):
            continue
        print(f'{symbol["location"]}: error: undocumented', file=sys.stderr)
        ok = False
    return ok


def collect_groups(blocks: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build the group list out of the @defgroup tags in `blocks`.

    The order is the order they were written in, which is the only ordering
    the author gave and the one a table of contents wants.
    """
    groups = []
    for block in blocks:
        doc = block['doc']
        for section in doc.of_kind(doc_parser.DEFGROUP):
            groups.append(
                {
                    'name': section.name,
                    # A group with no title reads by its own name.
                    'title': section.text or section.name,
                    'description': doc.description,
                    'doc': doc,
                    'location': block['location'],
                }
            )
    return groups


def warn_duplicate_symbols(symbols: Sequence[parse.Symbol]) -> None:
    """Report a name defined more than once across the sources read.

    CMake allows the redefinition, so this is a warning: the documentation
    would otherwise describe the same name twice with no hint of which
    definition wins.
    """
    first_seen: dict[str, parse.Symbol] = {}
    for symbol in symbols:
        earlier = first_seen.setdefault(symbol.name, symbol)
        if earlier is not symbol:
            print(
                f'{symbol.location}: warning: {symbol.name} is already '
                f'defined at {earlier.location}',
                file=sys.stderr,
            )


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
        content = rendering.inject(path.read_text(encoding='utf-8'), content, str(path))

    if check:
        if not path.exists():
            print(f'{path}: would be created', file=sys.stderr)
            return False
        current = path.read_text(encoding='utf-8')
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

    path.parent.mkdir(parents=True, exist_ok=True)
    # Explicit newline: on Windows the default would write CRLF, so generated
    # documentation would differ per platform and --check would never settle.
    path.write_text(content, encoding='utf-8', newline='\n')
    return True


def list_templates() -> int:
    for name in sorted(rendering.builtin_loader().list_templates()):
        print(name)
    return 0


def run(args: argparse.Namespace) -> int:
    if args.list_templates:
        return list_templates()

    pairs = validate_args(args)

    specs = [rendering.resolve_template_spec(spec) for spec, _ in pairs]
    # Most specific first: what the user asked for by -I, then the directory a
    # template was named by path from, and the working directory only as a
    # last resort before the built-ins.
    search_dirs = [pathlib.Path(d) for d in args.template_dir]
    search_dirs += [d for d, _ in specs if d is not None]
    search_dirs.append(pathlib.Path.cwd())

    env = rendering.build_environment(search_dirs)
    function_template = rendering.load_template(
        env, rendering.FUNCTION_TEMPLATE_NAME, search_dirs
    )

    symbols: list[parse.Symbol] = []
    commands: list[parse.Command] = []
    variables: list[parse.Variable] = []
    blocks: list[parse.Block] = []
    for path in collect_sources(
        args.path, args.exclude + read_ignore_file(pathlib.Path.cwd())
    ):
        file = parse.parse_file(path)
        symbols += parse.extract_symbols(file)
        commands += parse.extract_commands(file)
        variables += parse.extract_variables(file)
        blocks += parse.extract_blocks(file)
    warn_duplicate_symbols(symbols)

    # Groups first: what they define is what an @ingroup elsewhere is checked
    # against.
    documented_blocks = [enrich(b, None, args.strict) for b in blocks]
    groups = collect_groups(documented_blocks)
    known = frozenset(group['name'] for group in groups)

    context = {
        'symbols': [enrich(s, function_template, args.strict, known) for s in symbols],
        'commands': [enrich(c, None, args.strict, known) for c in commands],
        'variables': [enrich(v, None, args.strict, known) for v in variables],
        'groups': groups,
        'files': [b for b in documented_blocks if b['doc'].documents_file],
    }

    ok = True
    if args.require_docs:
        ok &= report_undocumented(context['symbols'])
    if args.json:
        content = serialize.dump(context)
        if args.json == STDOUT:
            sys.stdout.write(content)
        else:
            ok &= write_output(pathlib.Path(args.json), content, args.check)

    for (_, output), (_, name) in zip(pairs, specs, strict=True):
        template = rendering.load_template(env, name, search_dirs)
        content = rendering.render_document(template, context)
        if output == STDOUT:
            sys.stdout.write(content)
        else:
            ok &= write_output(pathlib.Path(output), content, args.check, args.inject)
    return 0 if ok else 1


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    try:
        return run(args)
    except Cmake2mdError as exc:
        print(f'cmake2md: error: {exc}', file=sys.stderr)
        return 1
    except jinja2.TemplateError as exc:
        print(f'cmake2md: template error: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
