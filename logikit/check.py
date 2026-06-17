#!/usr/bin/env python3
"""Statically verify the wiring of a generated ``.circ`` file.

Rendering a wrong circuit looks just as convincing as a right one, so before
trusting a figure you want a *connectivity* check that does not depend on
simulation.  This module parses the wires and component ports out of a
``.circ``, computes the nets using Logisim's own connection rules (wires joined
at shared endpoints or T-junctions; pure crossings do **not** connect), and
compares the resulting partition against the intended ``name.spec`` produced by
:mod:`logikit.circ`.

It catches the two ways wiring goes wrong:

* **shorts** — two intended nets that ended up merged into one node, and
* **opens**  — one intended net split across several nodes (or a floating pin).
"""
from __future__ import annotations

import json
import os
import re
import sys

# size-50 gates: output at (x,y); inputs at (x-DX, y +/- 20), plus a centre
# input for the 3-input case.  DX = body (50) + edge decorations (a 10px output
# bubble on NAND/NOR/XNOR, a 10px input arc on XOR/XNOR) -- verified against
# Logisim-evolution by reading each component's real ports.
_GRID_GATE_DX = {'AND Gate': 50, 'OR Gate': 50, 'NAND Gate': 60,
                 'NOR Gate': 60, 'XOR Gate': 60, 'XNOR Gate': 70}


def parse(circ: str):
    """Return ``(wires, comps)`` parsed from raw ``.circ`` text."""
    wires, comps = [], []
    for m in re.finditer(
            r'<wire from="\((-?\d+),(-?\d+)\)" to="\((-?\d+),(-?\d+)\)"/>', circ):
        x1, y1, x2, y2 = map(int, m.groups())
        wires.append(((x1, y1), (x2, y2)))
    for m in re.finditer(
            r'<comp lib="(\d+)" loc="\((-?\d+),(-?\d+)\)" name="([^"]+)">(.*?)</comp>'
            r'|<comp lib="(\d+)" loc="\((-?\d+),(-?\d+)\)" name="([^"]+)"/>', circ, re.S):
        if m.group(1):
            lib, x, y, name, body = (m.group(1), int(m.group(2)),
                                     int(m.group(3)), m.group(4), m.group(5))
        else:
            lib, x, y, name, body = (m.group(6), int(m.group(7)),
                                     int(m.group(8)), m.group(9), '')
        comps.append((lib, x, y, name, body))
    return wires, comps


def ports_of(lib, x, y, name, body):
    """Connection ports ``[(px, py), ...]`` of a single component."""
    if name == 'Pin':
        return [(x, y)]
    if name == 'NOT Gate':
        return [(x, y), (x - 30, y)]            # out, in
    if name in _GRID_GATE_DX:
        n = 2
        mm = re.search(r'name="inputs" val="(\d+)"', body)
        if mm:
            n = int(mm.group(1))
        dx = _GRID_GATE_DX[name]
        ins = ([(x - dx, y - 20), (x - dx, y + 20)] if n == 2 else
               [(x - dx, y - 20), (x - dx, y), (x - dx, y + 20)])
        return [(x, y)] + ins
    return []   # Text, etc.: no electrical ports


def on_seg(p, a, b):
    """True if point ``p`` lies on the axis-aligned segment ``a``--``b``."""
    (px, py), (ax, ay), (bx, by) = p, a, b
    if ax == bx:   # vertical
        return px == ax and min(ay, by) <= py <= max(ay, by)
    if ay == by:   # horizontal
        return py == ay and min(ax, bx) <= px <= max(ax, bx)
    return False


class UF:
    """Tiny union-find with path halving."""

    def __init__(self):
        self.p = {}

    def find(self, a):
        self.p.setdefault(a, a)
        while self.p[a] != a:
            self.p[a] = self.p[self.p[a]]
            a = self.p[a]
        return a

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[ra] = rb


def build_nets(wires, ports):
    """Union-find over wire endpoints + ports, applying Logisim's rules."""
    uf = UF()
    nodes = set(ports)
    for a, b in wires:
        nodes.add(a)
        nodes.add(b)
        uf.union(a, b)
    # any node lying on a wire segment (endpoint or T-junction) joins that wire
    for P in nodes:
        for a, b in wires:
            if on_seg(P, a, b):
                uf.union(P, a)
    return uf


def check(name, outdir='.'):
    """Check ``name.circ`` against ``name.spec``; print a report, return bool."""
    base = os.path.join(outdir, name)
    for ext in ('.circ', '.spec'):
        if not os.path.isfile(base + ext):
            raise FileNotFoundError(
                f"{base + ext!r} not found — generate it first, e.g. "
                f"emit('{name}', builder, {outdir!r}).")
    with open(base + '.circ') as f:
        circ = f.read()
    with open(base + '.spec') as f:
        spec = json.load(f)
    spec = {tuple(map(int, k.split(','))): v for k, v in spec.items()}

    wires, comps = parse(circ)
    allports = []
    for c in comps:
        allports += ports_of(*c)
    uf = build_nets(wires, allports)

    by_net, by_root, missing = {}, {}, []
    for port, net in spec.items():
        if port not in allports:
            missing.append((port, net))
        by_net.setdefault(net, []).append(port)
    root_of = {p: uf.find(p) for p in spec}
    for p, n in spec.items():
        by_root.setdefault(root_of[p], set()).add(n)

    ok = True
    for net, ports in by_net.items():                     # opens
        roots = {root_of[p] for p in ports}
        if len(roots) > 1:
            ok = False
            print(f"  [OPEN]  net '{net}' split across {len(roots)} nodes: {ports}")
    for root, nets in by_root.items():                    # shorts
        if len(nets) > 1:
            ok = False
            print(f"  [SHORT] nets {sorted(nets)} merged into one node")
    if missing:
        ok = False
        print(f"  [MISS]  spec ports not found as component ports: {missing}")

    total_nets = len({root_of[p] for p in spec})
    print(f"  {name}: {len(spec)} ports, {len(by_net)} intended nets, "
          f"{total_nets} actual nets -> {'OK' if ok else 'FAIL'}")
    return ok


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    outdir = '.'
    names = []
    for a in argv:
        if a.startswith('--dir='):
            outdir = a.split('=', 1)[1]
        else:
            names.append(a)
    if not names:
        print("usage: python -m logikit.check [--dir=DIR] NAME [NAME ...]")
        return 2
    return 0 if all(check(n, outdir) for n in names) else 1


if __name__ == '__main__':
    sys.exit(main())
