#!/usr/bin/env python3
"""Example schematics built with :mod:`logikit.circ`.

These are generic NAND/NOT building blocks chosen to exercise every feature of
the toolkit — multi-input gates, a NAND-built inverter, fan-out, feedback, and
the connectivity check / simulator — without being any particular textbook
assignment:

* ``mux2_nand``     — a 2:1 multiplexer ``Y = (A & ~S) | (B & S)`` from 1 NOT
                      and 3 NANDs.  Shows fan-out (``S`` drives two places) and
                      a perfectly valid wire *crossing* (no junction dot).
* ``and3_nand``     — a 3-input AND as ``NOT(NAND3(A, B, C))``.  Shows a
                      3-input gate and the NAND-inverter idiom.
* ``ring_osc_nand`` — three NAND-inverters in a loop.  Shows feedback routing
                      and the simulator reporting it as **unstable** (it
                      oscillates and never settles).

Run me to generate, verify and simulate all three::

    python -m examples.circuits            # -> build/*.circ, *_fig.circ, *.spec
    python -m examples.circuits --no-check # just generate
"""
from __future__ import annotations

import os
import sys

# Allow running straight from a checkout without installing the package.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from logikit.circ import emit          # noqa: E402
from logikit.check import check        # noqa: E402
from logikit.sim import truth_table    # noqa: E402


# ---------------------------------------------------------------------------
# 2:1 multiplexer:  Y = (A AND not S) OR (B AND S)
#   nS = NOT S ; g1 = NAND(A, nS) ; g2 = NAND(B, S) ; Y = NAND(g1, g2)
# ---------------------------------------------------------------------------
def mux2_nand(c):
    A = c.pin_in(90, 100, 'A')
    B = c.pin_in(90, 320, 'B')
    S = c.pin_in(90, 560, 'S')
    ns = c.notg(360, 300, label='nS')
    g1 = c.nand(560, 140)
    g2 = c.nand(560, 420)
    Y = c.nand(800, 290)
    Yo = c.pin_out(920, 290, 'Y')

    c.fan(A, 240, [g1['in'][0]], net='A')                 # A -> g1.in1
    c.fan(B, 280, [g2['in'][0]], net='B')                 # B -> g2.in1
    c.fan(S, 200, [ns['in'][0], g2['in'][1]], net='S')    # S -> NOT.in and g2.in2
    c.fan(ns['out'], 430, [g1['in'][1]], net='nS')        # nS -> g1.in2
    c.fan(g1['out'], 650, [Y['in'][0]], net='g1')         # g1 -> Y.in1
    c.fan(g2['out'], 690, [Y['in'][1]], net='g2')         # g2 -> Y.in2
    c.path(Y['out'], Yo)                                  # Y -> output
    c.mark('Y', Y['out'])


# ---------------------------------------------------------------------------
# 3-input AND from NANDs:  Y = NOT(NAND(A, B, C))
# ---------------------------------------------------------------------------
def and3_nand(c):
    A = c.pin_in(90, 100, 'A')
    B = c.pin_in(90, 200, 'B')
    C = c.pin_in(90, 300, 'C')
    n3 = c.nand(420, 200, n=3)
    inv = c.nand_inv(640, 200)
    Yo = c.pin_out(760, 200, 'Y')

    c.fan(A, 200, [n3['in'][0]], net='A')     # A -> top input
    c.fan(B, 240, [n3['in'][1]], net='B')     # B -> centre input
    c.fan(C, 160, [n3['in'][2]], net='C')     # C -> bottom input
    c.path(n3['out'], inv['in'][0])           # NAND3 -> inverter
    c.mark('nand3', n3['out'], *inv['pins'])
    c.path(inv['out'], Yo)                    # inverter -> output
    c.mark('Y', inv['out'])


# ---------------------------------------------------------------------------
# 3-stage NAND-inverter ring oscillator (odd inversions -> never settles)
# ---------------------------------------------------------------------------
def ring_osc_nand(c):
    i1 = c.nand_inv(300, 200)
    i2 = c.nand_inv(560, 200)
    i3 = c.nand_inv(820, 200)
    Yo = c.pin_out(960, 200, 'osc')

    c.path(i1['out'], i2['in'][0])            # stage 1 -> 2
    c.mark('a', i1['out'], *i2['pins'])
    c.path(i2['out'], i3['in'][0])            # stage 2 -> 3
    c.mark('b', i2['out'], *i3['pins'])
    c.path(i3['out'], Yo)                      # tap the loop as the output
    # stage 3 -> 1 feedback: up, across the top, back down the far left
    c.path(i3['out'], (820, 80), (180, 80), (180, 200), i1['in'][0])
    c.mark('c', i3['out'], *i1['pins'], Yo)


EXAMPLES = {
    'mux2_nand': mux2_nand,
    'and3_nand': and3_nand,
    'ring_osc_nand': ring_osc_nand,
}


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    do_check = '--no-check' not in argv
    outdir = 'build'
    names = [a for a in argv if not a.startswith('--')] or list(EXAMPLES)

    for name in names:
        emit(name, EXAMPLES[name], outdir)

    if do_check:
        print("\n--- connectivity check ---")
        ok = all(check(n, outdir) for n in names)
        print("\n--- simulation / truth tables ---")
        for n in names:
            truth_table(n, outdir)
        return 0 if ok else 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
