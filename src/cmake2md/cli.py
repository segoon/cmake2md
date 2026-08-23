"""Command line entry point."""

import argparse
import pathlib
import sys
from collections.abc import Sequence

import jinja2

from . import __version__
from . import config
from . import doc_parser
from . import output
from . import parse
from . import pipeline
from . import rendering
from . import serialize
from . import sources
from .errors import Cmake2mdError
from .errors import UsageError
from .output import list_templates
from .output import write_output
from .sources import IGNORE_FILE
from .sources import read_ignore_file

__all__ = [
    'IGNORE_FILE',
    'build_arg_parser',
    'main',
    'read_ignore_file',
    'run',
    'write_output',
]

#: The --output/--json value that means "write to stdout" instead of to a
#: file.  Defined in `config`, so that resolving a path setting against the
#: config file (`config._against`) knows to leave it alone.
STDOUT = config.STDOUT


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
        default=None,
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
        default=None,
        metavar='OUTPUT',
        help='Where to write the corresponding --template. Repeatable.',
    )
    parser.add_argument(
        '-I',
        '--template-dir',
        action='append',
        default=None,
        metavar='DIR',
        help='Additional directory to search for templates. Repeatable.',
    )
    parser.add_argument(
        '-c',
        '--config',
        metavar='FILE',
        help=(
            'Read the arguments from this TOML file. Without it, the nearest '
            f'{config.DEFAULT_FILE} at or above the working directory is '
            'used. Arguments given on the command line win.'
        ),
    )
    parser.add_argument(
        '--inject',
        action=argparse.BooleanOptionalAction,
        default=None,
        help=(
            'Write into an existing --output file, between its '
            f'{rendering.INJECT_BEGIN} and {rendering.INJECT_END} lines, '
            'instead of replacing the whole file. --no-inject wins over '
            'inject = true in the config file.'
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
        default=None,
        metavar='PATTERN',
        help=(
            'Skip source files matching this glob, against either the whole '
            'path or the file name. Repeatable.'
        ),
    )
    parser.add_argument(
        '--require-docs',
        action=argparse.BooleanOptionalAction,
        default=None,
        help=(
            'Exit non-zero if a public function() or macro() carries no doc '
            'comment. A name starting with _ is private and is not required '
            'to have one. --no-require-docs wins over require-docs = true in '
            'the config file.'
        ),
    )
    parser.add_argument(
        '--strict',
        action=argparse.BooleanOptionalAction,
        default=None,
        help=(
            'Treat documentation problems as errors: a doubtful @tag, and a '
            'doc comment that disagrees with the code it documents. On by '
            'default; --no-strict reports them as warnings and carries on.'
        ),
    )
    parser.add_argument(
        '--check',
        action=argparse.BooleanOptionalAction,
        default=None,
        help=(
            'Do not write anything; exit non-zero if any output is missing '
            'or differs from what is already on disk. --no-check wins over '
            'check = true in the config file.'
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
        default=None,
        metavar='CMAKE_FILE',
        help=(
            'CMake sources to read: files, directories to search for '
            'CMakeLists.txt and *.cmake, or glob patterns.'
        ),
    )
    return parser


def apply_config(args: argparse.Namespace, cwd: pathlib.Path) -> pathlib.Path | None:
    """Fill in from the config file whatever the command line left unsaid.

    The command line wins, always: a config file is where a project records
    what it usually does, not something that can override what was just asked
    for.  Returns the file it read, or None when there was none.
    """
    if args.config is None:
        path = config.find(cwd)
        if path is None:
            return None
    else:
        path = pathlib.Path(args.config)
        if not path.is_file():
            raise UsageError(f'no config file at {path}')

    for key, value in config.load(path).items():
        current = getattr(args, key, None)
        # Nothing was said on the command line: None for a flag, and either
        # None or empty for a list, which argparse fills in for a positional.
        # False is not the same as unsaid — the file must not win over an
        # explicit --no-strict.
        if current is None or current == []:
            setattr(args, key, value)
    return path


def apply_defaults(args: argparse.Namespace) -> None:
    """Settle whatever neither the command line nor the config file said.

    The defaults are the config model's own, so a setting cannot be given one
    there and another here.  A fresh `Settings()` each run also means the
    empty list a run fills in is never the list another run filled in.
    """
    for key, value in config.Settings().as_arguments().items():
        if getattr(args, key, None) is None:
            setattr(args, key, value)


def validate_args(
    args: argparse.Namespace, config_path: pathlib.Path | None = None
) -> list[tuple[str, str]]:
    # Where the missing setting was meant to come from is the useful half of
    # the message: a run with no arguments at all is one that expected a
    # config file to be found, and it was not.
    if config_path is None:
        source = f'and no {config.DEFAULT_FILE} found'
    else:
        source = f'by {config_path} or the command line'
    # --json alone is a legitimate run: a consumer that wants the parsed
    # model has no use for a template at all.
    if not args.template and not args.json:
        raise UsageError(f'no --template given {source}, nothing to render')
    if not args.path:
        raise UsageError(f'no CMAKE_FILE given {source}, nothing to read')
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
    for template, out in zip(args.template, args.output, strict=True):
        if out == STDOUT:
            continue
        key = str(pathlib.Path(out).resolve())
        if key in seen:
            raise UsageError(
                f'--output {out} is given twice, for {seen[key]} and '
                f'{template}; each template needs its own output'
            )
        seen[key] = template

    # The lengths are equal by the check above.
    return list(zip(args.template, args.output, strict=True))


def run(args: argparse.Namespace, cwd: pathlib.Path) -> int:
    if args.list_templates:
        return list_templates()

    config_path = apply_config(args, cwd)
    apply_defaults(args)
    pairs = validate_args(args, config_path)

    # The project root: where the config file was found, and so what the
    # paths in it were read against.
    root = config_path.parent if config_path else cwd

    specs = [rendering.resolve_template_spec(spec, cwd) for spec, _ in pairs]
    # Most specific first: what the user asked for by -I, then the directory a
    # template was named by path from, and the working directory only as a
    # last resort before the built-ins.
    search_dirs = [pathlib.Path(d) for d in args.template_dir]
    search_dirs += [d for d, _ in specs if d is not None]
    search_dirs.append(cwd)

    env = rendering.build_environment(search_dirs)
    function_template = rendering.load_template(
        env, rendering.FUNCTION_TEMPLATE_NAME, search_dirs
    )

    rules = pipeline.DocRules(
        specs=doc_parser.vocabulary(args.tags),
        strict=args.strict,
    )

    symbols: list[parse.Symbol] = []
    commands: list[parse.Command] = []
    variables: list[parse.Variable] = []
    blocks: list[parse.Block] = []
    exclude = args.exclude + sources.read_ignore_file(root)
    for path in sources.collect_sources(args.path, exclude):
        file = parse.parse_file(path)
        symbols += parse.extract_symbols(file)
        commands += parse.extract_commands(file)
        variables += parse.extract_variables(file)
        blocks += parse.extract_blocks(file)
    pipeline.warn_duplicate_symbols(symbols)

    # Shared across every enrich() call below: an option()/set(... CACHE ...)
    # is read once as a Command and once as the Variable it also is, over the
    # same comment, and this is what keeps its diagnostics from printing twice.
    reported: set[tuple[str, int]] = set()

    # Groups first: what they define is what an @ingroup elsewhere is checked
    # against, including an @ingroup inside a standalone block itself, so
    # checking those blocks is deferred until every one has been read.
    documented_blocks = [
        pipeline.enrich(b, rules, reported=reported, check_now=False) for b in blocks
    ]
    groups = pipeline.collect_groups(documented_blocks)
    known = frozenset(group['name'] for group in groups)
    for block, doc_block in zip(blocks, documented_blocks, strict=True):
        pipeline.check_and_report(block, doc_block['doc'], known, rules, reported)

    enriched_symbols = [pipeline.enrich(s, rules, known, reported) for s in symbols]
    # Every symbol is enriched before any of them is rendered, so @see can
    # resolve a name against the whole list rather than always missing.
    pipeline.render_symbols(enriched_symbols, function_template)

    context = {
        'symbols': enriched_symbols,
        # Variables first, so a warning about an option()/set(... CACHE ...)
        # is reported under its own name rather than the generic 'command'.
        'variables': [pipeline.enrich(v, rules, known, reported) for v in variables],
        'commands': [pipeline.enrich(c, rules, known, reported) for c in commands],
        'groups': groups,
        'files': [b for b in documented_blocks if b['doc'].documents_file],
    }

    ok = True
    if args.require_docs:
        ok &= pipeline.report_undocumented(context['symbols'])
    if args.json:
        content = serialize.dump(context)
        if args.json == STDOUT:
            sys.stdout.write(content)
        else:
            ok &= output.write_output(pathlib.Path(args.json), content, args.check)

    for (_, out), (_, name) in zip(pairs, specs, strict=True):
        template = rendering.load_template(env, name, search_dirs)
        content = rendering.render_document(template, context)
        if out == STDOUT:
            sys.stdout.write(content)
        else:
            ok &= output.write_output(
                pathlib.Path(out), content, args.check, args.inject
            )
    return 0 if ok else 1


def main(argv: Sequence[str] | None = None, cwd: pathlib.Path | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    try:
        return run(args, cwd if cwd is not None else pathlib.Path.cwd())
    except Cmake2mdError as exc:
        print(f'cmake2md: error: {exc}', file=sys.stderr)
        return 1
    except jinja2.TemplateError as exc:
        print(f'cmake2md: template error: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
