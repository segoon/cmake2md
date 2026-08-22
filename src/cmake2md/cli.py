"""Command line entry point."""

import argparse
import dataclasses
import pathlib
import sys
from collections.abc import Sequence
from typing import Any

import jinja2

from . import __version__
from . import doc_parser
from . import parse
from . import rendering
from . import tag_lexer
from .errors import Cmake2mdError
from .errors import ParseError
from .errors import UsageError


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
        '--strict',
        action='store_true',
        help='Treat unknown @tags as errors instead of literal text.',
    )
    parser.add_argument(
        '--check',
        action='store_true',
        help=(
            'Do not write anything; exit non-zero if any output would '
            'differ from what is already on disk.'
        ),
    )
    parser.add_argument(
        'path', nargs='+', metavar='CMAKE_FILE', help='CMake sources to read.'
    )
    return parser


def validate_args(args: argparse.Namespace) -> list[tuple[str, str]]:
    if not args.template:
        raise UsageError('no --template given, nothing to render')
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
    # The lengths are equal by the check above.
    return list(zip(args.template, args.output, strict=True))


def enrich(
    item: parse.Symbol | parse.Command,
    function_template: jinja2.Template | None,
    strict: bool,
) -> dict[str, Any]:
    """Attach the parsed doc comment and a rendered form to `item`."""
    try:
        doc = doc_parser.parse(tag_lexer.tokenize(item.comments), strict=strict)
    except ParseError as exc:
        raise exc.at(item.location) from None

    for warning in doc.warnings:
        print(f'{item.location}: warning: {warning}', file=sys.stderr)

    res = dataclasses.asdict(item)
    res['doc'] = doc
    res['group'] = doc.group
    res['location'] = item.location
    if function_template is not None:
        res['pretty'] = function_template.render({'symbol': res}).strip()
    else:
        res['pretty'] = doc.description
    return res


def write_output(path: pathlib.Path, content: str, check: bool) -> bool:
    """Write `content`, or in check mode report whether it is up to date."""
    if check:
        if not path.exists():
            print(f'{path}: would be created', file=sys.stderr)
            return False
        if path.read_text(encoding='utf-8') == content:
            return True
        print(f'{path}: out of date', file=sys.stderr)
        return False

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding='utf-8', newline='\n')
    return True


def run(args: argparse.Namespace) -> int:
    pairs = validate_args(args)

    specs = [rendering.resolve_template_spec(spec) for spec, _ in pairs]
    search_dirs = [pathlib.Path(d) for d in args.template_dir]
    search_dirs += [d for d, _ in specs if d is not None]
    search_dirs.append(pathlib.Path.cwd())

    env = rendering.build_environment(search_dirs)
    function_template = rendering.load_template(
        env, rendering.FUNCTION_TEMPLATE_NAME, search_dirs
    )

    symbols: list[parse.Symbol] = []
    commands: list[parse.Command] = []
    for path in args.path:
        file = parse.parse_file(path)
        symbols += parse.extract_symbols(file)
        commands += parse.extract_commands(file)

    context = {
        'symbols': [enrich(s, function_template, args.strict) for s in symbols],
        'commands': [enrich(c, None, args.strict) for c in commands],
    }

    ok = True
    for (_, output), (_, name) in zip(pairs, specs, strict=True):
        template = rendering.load_template(env, name, search_dirs)
        content = rendering.render_document(template, context)
        ok &= write_output(pathlib.Path(output), content, args.check)
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
