#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Example breadboard wiring diagram built with :mod:`logikit.wiring`.

``wiring_mux2`` realises the same 2:1 multiplexer as ``examples.circuits`` on a
single 74LS00 quad-NAND DIP, and patches its inputs to the power box's
electrode keys.  The output is read on the logic box's built-in pin LED, so it
is deliberately *not* wired back to the power box.

74LS00 gate map (output pin <- its two input pins)::

    3 <- (1, 2)    6 <- (4, 5)    8 <- (9, 10)    11 <- (12, 13)
    Vcc = 14,  GND = 7

Assignment::

    gate @3  : nS = NOT S      (pins 1,2 tied to S)
    gate @6  : g1 = NAND(A, nS)
    gate @8  : g2 = NAND(B, S)
    gate @11 : Y  = NAND(g1, g2)   <- read on the pin-11 LED

Run me (needs ``lualatex`` + a CJK font, or set ASCII labels — see below)::

    python -m examples.breadboard      # -> build/wiring_mux2.pdf
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from logikit.wiring import Scene, render_scene   # noqa: E402


def wiring_mux2():
    s = Scene(1)
    s.ic_tags = {0: "IC1"}
    s.elec_labels = {1: "$A$", 2: "$B$", 3: "$S$"}
    # For an all-Latin figure (no CJK font needed) uncomment:
    # s.logic_label, s.power_label = "Logic box", "Power box"

    s.net([('E', 1), ('P', 0, 4)])                              # A  -> g1.in1
    s.net([('E', 2), ('P', 0, 9)], side='L')                    # B  -> g2.in1
    s.net([('E', 3), ('P', 0, 1), ('P', 0, 2), ('P', 0, 10)])   # S  -> NOT tie + g2.in2
    s.net([('P', 0, 3), ('P', 0, 5)])                           # nS -> g1.in2
    s.net([('P', 0, 6), ('P', 0, 12)])                          # g1 -> Y.in1
    s.net([('P', 0, 8), ('P', 0, 13)])                          # g2 -> Y.in2
    # Y = output on pin 11, read on the logic-box LED (not wired to power box).
    s.gnd_net()
    s.vcc_net()
    return s


SCENES = {'wiring_mux2': wiring_mux2}


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    outdir = 'build'
    names = [a for a in argv if not a.startswith('--')] or list(SCENES)
    for name in names:
        render_scene(SCENES[name](), name, outdir)
    return 0


if __name__ == '__main__':
    sys.exit(main())
