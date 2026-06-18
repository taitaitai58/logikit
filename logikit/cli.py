#!/usr/bin/env python3
"""Unified command-line entry point: ``logikit <command> ...``.

A single front door for the operations that act on files already on disk —
``check`` and ``sim`` (with Markdown/LaTeX export) — plus ``doctor`` (the
environment report) and ``examples`` (regenerate the bundled example circuits).

Generating an *arbitrary* circuit stays a Python-API task: a builder is code
(``fn(c)`` placing gates and routing wires), not something expressible as flags,
so use :func:`logikit.circ.emit` for that.  ``logikit examples`` is the closest
CLI shortcut and (re)builds the demo circuits shipped in ``examples/``.

Installed as the ``logikit`` console script (see ``pyproject.toml``); also
runnable as ``python -m logikit``.
"""
from __future__ import annotations

import argparse
import sys


def _build_parser():
    p = argparse.ArgumentParser(
        prog='logikit',
        description='Generate, verify and inspect digital-logic figures.')
    sub = p.add_subparsers(dest='cmd')

    pc = sub.add_parser('check', help='static connectivity check of NAME.circ '
                                      'against NAME.spec (shorts / opens)')
    pc.add_argument('names', nargs='+', metavar='NAME')
    pc.add_argument('--dir', default='.', metavar='DIR',
                    help='directory holding the .circ/.spec files (default: .)')

    ps = sub.add_parser('sim', help='truth table / oscillation check of NAME.circ')
    ps.add_argument('names', nargs='+', metavar='NAME')
    ps.add_argument('--dir', default='.', metavar='DIR',
                    help='directory holding the .circ files (default: .)')
    ps.add_argument('--format', choices=['md', 'latex'], default=None,
                    help='emit the table as Markdown or LaTeX instead of text')

    sub.add_parser('doctor', help='report which capabilities work here and how '
                                  'to install whatever is missing')

    sub.add_parser('examples', help='(re)generate the bundled example circuits '
                                    'into build/ and verify them; extra args '
                                    '(e.g. --no-check) pass through')

    return p


def _run_examples(passthrough):
    try:
        from examples.circuits import main as examples_main
    except ImportError:
        print("error: the bundled examples are only available from a source "
              "checkout (they ship in examples/, not in the installed package). "
              "Clone the repo and run this from its root.", file=sys.stderr)
        return 2
    return examples_main(passthrough)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv

    # `examples` is a pure pass-through to examples.circuits, so intercept it
    # before argparse (which can't cleanly forward leading --flags via REMAINDER).
    if argv and argv[0] == 'examples':
        return _run_examples(argv[1:])

    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.cmd == 'check':
        from .check import check
        return 0 if all(check(n, args.dir) for n in args.names) else 1

    if args.cmd == 'sim':
        from .sim import truth_table, truth_table_str
        for n in args.names:
            if args.format:
                print(truth_table_str(n, args.dir, args.format))
                print()
            else:
                truth_table(n, args.dir)
        return 0

    if args.cmd == 'doctor':
        from .doctor import main as doctor_main
        return doctor_main([])

    parser.print_help()
    return 0


if __name__ == '__main__':
    sys.exit(main())
