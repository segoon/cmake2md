"""Command line entry point."""

import argparse
import pathlib
import sys
from collections.abc import Sequence
from typing import NamedTuple

import jinja2

from . import __version__
from . import config
from . import doc_parser
from . import entries
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
        prog='cmake2doc',
        description=(
            'Generate documentation from CMake sources by extracting '
            'doxygen-like comments and rendering them with Jinja templates.'
        ),
    )
    parser.add_argument(
        '--version',
        action='version',
        version=f'cmake2doc {__version__}',
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
            f'{rendering.MARKDOWN_MARKERS.begin} and '
            f'{rendering.MARKDOWN_MARKERS.end} lines (or, for a .rst output, '
            f'{rendering.RST_MARKERS.begin} and {rendering.RST_MARKERS.end}), '
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


def find_config(config_arg: str | None, cwd: pathlib.Path) -> pathlib.Path | None:
    """The config file this run reads: `--config`'s value if given, else
    the nearest cmake2doc.toml at or above `cwd`.
    """
    if config_arg is None:
        return config.find(cwd)
    path = pathlib.Path(config_arg)
    if not path.is_file():
        raise UsageError(f'no config file at {path}')
    return path


def resolve_args(ns: argparse.Namespace, file: config.Settings) -> config.Settings:
    """The command line over `file` (already the config file over the
    built-in defaults, via `config.resolve()`) — the command line always
    wins, when it said anything at all.

    The one place this module reads `argparse.Namespace` attributes, which
    are untyped by construction; everything built from this function's
    result is the typed `config.Settings` it returns.  A positional's
    "nothing given" is `[]`, not `None` — `or` treats both as unsaid, same
    as every list flag's `None`.
    """
    return config.Settings(
        template=ns.template or file.template,
        output=ns.output or file.output,
        template_dir=ns.template_dir or file.template_dir,
        path=ns.path or file.path,
        exclude=ns.exclude or file.exclude,
        json=ns.json if ns.json is not None else file.json,
        inject=ns.inject if ns.inject is not None else file.inject,
        check=ns.check if ns.check is not None else file.check,
        require_docs=(
            ns.require_docs if ns.require_docs is not None else file.require_docs
        ),
        strict=ns.strict if ns.strict is not None else file.strict,
        # No --tags option: a vocabulary is a property of the project, not
        # of a single run, so this only ever comes from the file.
        tags=file.tags,
    )


class TemplateOutput(NamedTuple):
    template: str
    output: str


def validate_args(
    args: config.Settings, config_path: pathlib.Path | None = None
) -> list[TemplateOutput]:
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
    return [
        TemplateOutput(template, out)
        for template, out in zip(args.template, args.output, strict=True)
    ]


def run(raw_args: argparse.Namespace, cwd: pathlib.Path) -> int:
    if raw_args.list_templates:
        return list_templates()

    config_path = find_config(raw_args.config, cwd)
    args = resolve_args(raw_args, config.resolve(config_path))
    pairs = validate_args(args, config_path)

    # The project root: where the config file was found, and so what the
    # paths in it were read against.
    root = config_path.parent if config_path else cwd

    specs = [rendering.resolve_template_spec(pair.template, cwd) for pair in pairs]
    # Most specific first: what the user asked for by -I, then the directory a
    # template was named by path from, and the working directory only as a
    # last resort before the built-ins.
    search_dirs = [pathlib.Path(d) for d in args.template_dir]
    search_dirs += [spec.search_dir for spec in specs if spec.search_dir is not None]
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
    targets: list[parse.Target] = []
    blocks: list[parse.Block] = []
    exclude = args.exclude + sources.read_ignore_file(root)
    for path in sources.collect_sources(args.path, exclude):
        file = parse.parse_file(path)
        symbols += parse.extract_symbols(file)
        commands += parse.extract_commands(file)
        variables += parse.extract_variables(file)
        targets += parse.extract_targets(file)
        blocks += parse.extract_blocks(file)
    pipeline.warn_duplicate_symbols(symbols)

    # Shared across every enrich() call below: an option()/set(... CACHE ...)
    # or an add_library()/add_executable()/add_test()/add_custom_target() is
    # read once as a Command and once as the Variable/Target it also is, over
    # the same comment, and this is what keeps its diagnostics from printing
    # twice.
    reported: set[pipeline.ReportKey] = set()

    # Groups first: what they define is what an @ingroup elsewhere is checked
    # against, including an @ingroup inside a standalone block itself, so
    # checking those blocks is deferred until every one has been read.
    documented_blocks = [
        pipeline.enrich_block(b, rules, reported=reported, check_now=False)
        for b in blocks
    ]
    groups = pipeline.collect_groups(documented_blocks)
    known = frozenset(group.name for group in groups)
    for block, doc_block in zip(blocks, documented_blocks, strict=True):
        pipeline.check_and_report(block, doc_block.doc, known, rules, reported)

    enriched_symbols = [
        pipeline.enrich_symbol(s, rules, known, reported) for s in symbols
    ]
    # Every symbol is enriched before any of them is rendered, so @see can
    # resolve a name against the whole list rather than always missing.
    pipeline.render_symbols(enriched_symbols, function_template)

    context = entries.Context(
        symbols=enriched_symbols,
        # Variables and targets first, so a warning about an
        # option()/set(... CACHE ...) or an add_library()/add_executable()/
        # add_test()/add_custom_target() is reported under its own name
        # rather than the generic 'command'.
        variables=[
            pipeline.enrich_variable(v, rules, known, reported) for v in variables
        ],
        targets=[pipeline.enrich_target(t, rules, known, reported) for t in targets],
        commands=[pipeline.enrich_command(c, rules, known, reported) for c in commands],
        groups=groups,
        files=[b for b in documented_blocks if b.doc.documents_file],
    )

    ok = True
    if args.require_docs:
        ok &= pipeline.report_undocumented(context.symbols)
    if args.json:
        content = serialize.dump(context)
        if args.json == STDOUT:
            sys.stdout.write(content)
        else:
            ok &= output.write_output(pathlib.Path(args.json), content, args.check)

    for pair, spec in zip(pairs, specs, strict=True):
        template = rendering.load_template(env, spec.name, search_dirs)
        content = rendering.render_document(template, context)
        if pair.output == STDOUT:
            sys.stdout.write(content)
        else:
            ok &= output.write_output(
                pathlib.Path(pair.output), content, args.check, args.inject
            )
    return 0 if ok else 1


def main(argv: Sequence[str] | None = None, cwd: pathlib.Path | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    try:
        return run(args, cwd if cwd is not None else pathlib.Path.cwd())
    except Cmake2mdError as exc:
        print(f'cmake2doc: error: {exc}', file=sys.stderr)
        return 1
    except jinja2.TemplateError as exc:
        print(f'cmake2doc: template error: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
