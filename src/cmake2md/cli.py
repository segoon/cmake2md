"""Command line entry point."""

import argparse
import dataclasses
import difflib
import fnmatch
import glob
import pathlib
import sys
from collections.abc import Mapping
from collections.abc import Sequence
from typing import Any

import jinja2

from . import __version__
from . import checks
from . import config
from . import doc_parser
from . import parse
from . import rendering
from . import serialize
from . import tag_lexer
from .errors import Cmake2mdError
from .errors import ParseError
from .errors import UsageError

#: The --output/--json value that means "write to stdout" instead of to a
#: file.  Defined in `config`, so that resolving a path setting against the
#: config file (`config._against`) knows to leave it alone.
STDOUT = config.STDOUT
#: What a directory given as CMAKE_FILE is searched for.
SOURCE_GLOBS = ('CMakeLists.txt', '*.cmake')
#: File listing extra --exclude patterns, one per line, '#' starting a comment.
IGNORE_FILE = '.cmake2mdignore'

#: The empty value of each `config.Kind` that has one; a setting of that kind
#: defaults to it unless `_DEFAULT_OVERRIDES` says otherwise.  `Kind.Str` is
#: not here: `json`'s only setting of that kind takes no option on the command
#: line, so it has no `None`-vs-unset ambiguity for a default to settle.
_KIND_DEFAULTS: dict[config.Kind, list[str] | bool | dict[str, doc_parser.TagSpec]] = {
    config.Kind.List: [],
    config.Kind.Bool: False,
    config.Kind.Tags: {},
}
#: Settings whose default is not their kind's empty value.
_DEFAULT_OVERRIDES: dict[str, bool] = {'strict': True}

#: What each optional argument is worth when neither the command line nor the
#: config file says.  argparse leaves them all None instead, so that silence is
#: told apart from an explicit --no-strict, which the config file must not win
#: over.  Derived from `config.KEYS` so the two cannot drift apart: every
#: setting a project can put in `cmake2md.toml` has a default here too.
DEFAULTS: dict[str, list[str] | bool | dict[str, doc_parser.TagSpec]] = {
    name: _DEFAULT_OVERRIDES.get(name, _KIND_DEFAULTS[kind])
    for name, kind in config.KEYS.items()
    if kind in _KIND_DEFAULTS
}


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


def apply_config(args: argparse.Namespace) -> pathlib.Path | None:
    """Fill in from the config file whatever the command line left unsaid.

    The command line wins, always: a config file is where a project records
    what it usually does, not something that can override what was just asked
    for.  Returns the file it read, or None when there was none.
    """
    if args.config is None:
        path = config.find(pathlib.Path.cwd())
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
    """Settle whatever neither the command line nor the config file said."""
    for key, value in DEFAULTS.items():
        if getattr(args, key, None) is not None:
            continue
        # A copy: the empty default must not be shared between runs.
        if isinstance(value, (list, dict)):
            setattr(args, key, value.copy())
        else:
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


@dataclasses.dataclass(frozen=True)
class DocRules:
    """How a doc comment is read: the vocabulary, and how loudly to complain."""

    specs: Mapping[str, doc_parser.TagSpec]
    strict: bool


def enrich(
    item: parse.Documented,
    rules: DocRules,
    groups: frozenset[str] = frozenset(),
    reported: set[tuple[str, int]] | None = None,
) -> dict[str, Any]:
    """Attach the parsed doc comment to `item`.

    `pretty` starts out as the plain description; `render_symbols` overwrites
    it for a `Symbol`, once every symbol has been enriched. A command call has
    no signature of its own for the function template to render, so its
    description is all `pretty` will ever be.

    An `option()` or `set(... CACHE ...)` call is read twice — once as a
    `Command`, once as the `Variable` it also is — over the very same comment.
    `reported` is how the two are kept from printing every diagnostic about it
    twice: it is shared across a whole run, and a comment block is reported
    only the first time its (file, line) is seen.
    """
    try:
        doc = doc_parser.parse(
            tag_lexer.tokenize(item.comments),
            strict=rules.strict,
            first_line=item.comments_line or item.line,
            specs=rules.specs,
        )
    except ParseError as exc:
        raise exc.at(item.location_at(exc.line)) from None

    # comments_line is 0 for an item with no comment at all, which carries no
    # warnings to begin with, so nothing is lost by not deduplicating that.
    key = (item.filepath, item.comments_line)
    if reported is None or item.comments_line == 0 or key not in reported:
        report(item, doc.warnings + checks.check(item, doc, groups), rules.strict)
        if reported is not None and item.comments_line:
            reported.add(key)

    res = dataclasses.asdict(item)
    res['doc'] = doc
    res['group'] = doc.group
    res['location'] = item.location
    res['pretty'] = doc.description
    return res


def render_symbols(
    symbols: Sequence[dict[str, Any]], function_template: jinja2.Template
) -> None:
    """Fill in `pretty` for every enriched symbol, in place.

    Done only once every symbol is enriched, and given the whole list, so
    that `symbol_link` inside the function template can resolve an `@see`
    naming another symbol in the same run instead of always missing.
    """
    for symbol in symbols:
        symbol['pretty'] = function_template.render(
            {'symbol': symbol, 'symbols': symbols}
        ).strip()


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
    the author gave and the one a table of contents wants. A name given to
    more than one @defgroup is a warning rather than a second entry: nothing
    would tell a reader which of the two definitions a symbol in that group
    belongs under.
    """
    groups = []
    first_seen: dict[str, str] = {}
    for block in blocks:
        doc = block['doc']
        for section in doc.of_kind(doc_parser.DEFGROUP):
            earlier = first_seen.setdefault(section.name, block['location'])
            if earlier != block['location']:
                print(
                    f'{block["location"]}: warning: @defgroup {section.name} '
                    f'is already defined at {earlier}',
                    file=sys.stderr,
                )
                continue
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


def run(args: argparse.Namespace) -> int:
    if args.list_templates:
        return list_templates()

    config_path = apply_config(args)
    apply_defaults(args)
    pairs = validate_args(args, config_path)

    # The project root: where the config file was found, and so what the
    # paths in it were read against.
    root = config_path.parent if config_path else pathlib.Path.cwd()

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

    rules = DocRules(
        specs=doc_parser.vocabulary(args.tags),
        strict=args.strict,
    )

    symbols: list[parse.Symbol] = []
    commands: list[parse.Command] = []
    variables: list[parse.Variable] = []
    blocks: list[parse.Block] = []
    for path in collect_sources(args.path, args.exclude + read_ignore_file(root)):
        file = parse.parse_file(path)
        symbols += parse.extract_symbols(file)
        commands += parse.extract_commands(file)
        variables += parse.extract_variables(file)
        blocks += parse.extract_blocks(file)
    warn_duplicate_symbols(symbols)

    # Shared across every enrich() call below: an option()/set(... CACHE ...)
    # is read once as a Command and once as the Variable it also is, over the
    # same comment, and this is what keeps its diagnostics from printing twice.
    reported: set[tuple[str, int]] = set()

    # Groups first: what they define is what an @ingroup elsewhere is checked
    # against.
    documented_blocks = [enrich(b, rules, reported=reported) for b in blocks]
    groups = collect_groups(documented_blocks)
    known = frozenset(group['name'] for group in groups)

    enriched_symbols = [enrich(s, rules, known, reported) for s in symbols]
    # Every symbol is enriched before any of them is rendered, so @see can
    # resolve a name against the whole list rather than always missing.
    render_symbols(enriched_symbols, function_template)

    context = {
        'symbols': enriched_symbols,
        # Variables first, so a warning about an option()/set(... CACHE ...)
        # is reported under its own name rather than the generic 'command'.
        'variables': [enrich(v, rules, known, reported) for v in variables],
        'commands': [enrich(c, rules, known, reported) for c in commands],
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
