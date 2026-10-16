"""Command line interface: ``statement-ratios analyze FILE`` and ``statement-ratios schema``."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence

from . import __version__
from .analysis import analyze
from .loader import load_company
from .models import InputError, ValidationError
from .report import RENDERERS
from .schema import describe, template
from .validate import DEFAULT_TOLERANCE


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="statement-ratios",
        description="Financial statement ratio analysis from JSON or CSV statements.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    an = sub.add_parser("analyze", help="compute and interpret ratios for a statements file")
    an.add_argument("file", help="path to a .json or .csv file (see 'schema')")
    an.add_argument("--year", type=int, help="analyse only this fiscal year")
    an.add_argument(
        "--format",
        choices=sorted(RENDERERS),
        default="table",
        help="output format (default: table)",
    )
    an.add_argument(
        "--tolerance",
        type=float,
        default=DEFAULT_TOLERANCE,
        help="balance sheet tolerance as a fraction of total assets "
        f"(default: {DEFAULT_TOLERANCE})",
    )

    sc = sub.add_parser("schema", help="print the expected input schema and a template")
    sc.add_argument("--template", action="store_true", help="print only the JSON template")
    return parser


def _report_error(exc: InputError) -> None:
    if isinstance(exc, ValidationError) and len(exc.errors) > 1:
        print(f"error: {len(exc.errors)} problems found in the input:", file=sys.stderr)
        for problem in exc.errors:
            print(f"  - {problem}", file=sys.stderr)
    else:
        print(f"error: {exc}", file=sys.stderr)


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "schema":
        if not args.template:
            print(describe())
        print(json.dumps(template(), indent=2))
        return 0
    try:
        if args.tolerance < 0:
            raise InputError("--tolerance must not be negative")
        company = load_company(args.file, args.tolerance)
        result = analyze(company, args.year)
    except InputError as exc:
        _report_error(exc)
        return 1
    sys.stdout.write(RENDERERS[args.format](result))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
