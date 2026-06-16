#!/usr/bin/env python3
"""Extract a gate-level netlist from a ``.circ`` and simulate it.

This is a tiny, dependency-free logic simulator built for *checking figures*,
not for performance.  It reuses the same net model as :mod:`logikit.check`
(wires joined at shared endpoints / T-junctions), turns every gate into a
``(kind, [in_nets], out_net)`` triple, and relaxes the network to a fixpoint
with a Gauss-Seidel sweep.

Because it iterates to a fixpoint, it handles feedback too: a cross-coupled
latch settles to a stable state, while a ring oscillator never converges and is
reported as **unstable** rather than silently returning a bogus value.
"""
from __future__ import annotations

import itertools
import os
import re
import sys

from .check import UF, on_seg

# Boolean function of each gate kind, given the list of input values (0/1).
# Logisim-evolution's *default* XOR/XNOR is "exactly one input high"
# (computeExactlyOne), NOT odd parity — they agree for 2 inputs but differ for
# 3+.  A comp carrying `<a name="xor" val="odd"/>` uses odd parity instead; the
# netlist tags those as XOR_ODD / XNOR_ODD so simulation matches what Logisim
# would actually compute for the same .circ.
_EVAL = {
    'NAND': lambda vs: 0 if all(v == 1 for v in vs) else 1,
    'AND':  lambda vs: 1 if all(v == 1 for v in vs) else 0,
    'OR':   lambda vs: 1 if any(v == 1 for v in vs) else 0,
    'NOR':  lambda vs: 0 if any(v == 1 for v in vs) else 1,
    'XOR':  lambda vs: 1 if sum(vs) == 1 else 0,        # Logisim default
    'XNOR': lambda vs: 0 if sum(vs) == 1 else 1,
    'XOR_ODD':  lambda vs: sum(vs) % 2,                 # xor val="odd"
    'XNOR_ODD': lambda vs: 1 - (sum(vs) % 2),
    'NOT':  lambda vs: 1 - vs[0],
}

_KIND = {'NAND Gate': 'NAND', 'AND Gate': 'AND', 'OR Gate': 'OR',
         'NOR Gate': 'NOR', 'XOR Gate': 'XOR', 'XNOR Gate': 'XNOR',
         'NOT Gate': 'NOT'}


def parse_circ(path):
    """Return ``(wires, comps)`` from a ``.circ`` file path."""
    with open(path) as f:
        circ = f.read()
    wires = []
    for m in re.finditer(
            r'<wire from="\((-?\d+),(-?\d+)\)" to="\((-?\d+),(-?\d+)\)"/>', circ):
        x1, y1, x2, y2 = map(int, m.groups())
        wires.append(((x1, y1), (x2, y2)))
    comps = []
    for m in re.finditer(
            r'<comp lib="(\d+)" loc="\((-?\d+),(-?\d+)\)" name="([^"]+)">(.*?)</comp>'
            r'|<comp lib="(\d+)" loc="\((-?\d+),(-?\d+)\)" name="([^"]+)"/>',
            circ, re.S):
        if m.group(1):
            lib, x, y, name, body = (m.group(1), int(m.group(2)),
                                     int(m.group(3)), m.group(4), m.group(5))
        else:
            lib, x, y, name, body = (m.group(6), int(m.group(7)),
                                     int(m.group(8)), m.group(9), '')
        comps.append((lib, x, y, name, body))
    return wires, comps


def _build_uf(wires, ports):
    uf = UF()
    nodes = set(ports)
    for a, b in wires:
        nodes.add(a)
        nodes.add(b)
        uf.union(a, b)
    for P in nodes:
        for a, b in wires:
            if on_seg(P, a, b):
                uf.union(P, a)
    return uf


def netlist_from_circ(name, outdir='.'):
    """Return ``(gates, inputs, outputs)`` for ``name.circ``.

    ``gates`` is a list of ``(kind, [in_net, ...], out_net)``; ``inputs`` and
    ``outputs`` map each ``Pin`` label to its net.  Nets are union-find roots
    (opaque coordinate tuples) — compare them, don't interpret them.
    """
    wires, comps = parse_circ(os.path.join(outdir, name + '.circ'))
    ports, metas = [], []
    for (lib, x, y, nm, body) in comps:
        if nm == 'Pin':
            lab = re.search(r'name="label" val="([^"]+)"', body)
            isout = re.search(r'name="output" val="true"', body) is not None
            ports.append((x, y))
            metas.append(('Pin', (x, y), lab.group(1) if lab else '?', isout))
        elif nm == 'NOT Gate':
            o, i = (x, y), (x - 30, y)
            ports += [o, i]
            metas.append(('NOT', o, [i]))
        elif nm in _KIND:
            n = 2
            mm = re.search(r'name="inputs" val="(\d+)"', body)
            if mm:
                n = int(mm.group(1))
            o = (x, y)
            ins = ([(x - 50, y - 20), (x - 50, y + 20)] if n == 2 else
                   [(x - 50, y - 20), (x - 50, y), (x - 50, y + 20)])
            ports += [o] + ins
            kind = _KIND[nm]
            if kind in ('XOR', 'XNOR') and re.search(r'name="xor" val="odd"', body):
                kind += '_ODD'                          # odd-parity variant
            metas.append((kind, o, ins))
    uf = _build_uf(wires, ports)
    R = uf.find

    gates, inputs, outputs = [], {}, {}
    for meta in metas:
        if meta[0] == 'Pin':
            _, loc, label, isout = meta
            (outputs if isout else inputs)[label] = R(loc)
        else:
            kind, o, ins = meta
            gates.append((kind, [R(p) for p in ins], R(o)))
    return gates, inputs, outputs


def simulate(gates, in_vals, seed=None, max_pass=2000):
    """Relax ``gates`` to a fixpoint.

    ``in_vals`` forces source nets (the inputs); ``seed`` sets the initial value
    of latch nets so a bistable circuit lands in a chosen state.  Returns
    ``(stable, {net: value})``; ``stable=False`` means no fixpoint was reached
    within ``max_pass`` sweeps (an oscillator).
    """
    val = {}
    allnets = set(in_vals)
    for kind, ins, out in gates:
        allnets.update(n for n in ins if n is not None)
        allnets.add(out)
    for n in allnets:
        val[n] = 1
    if seed:
        val.update(seed)
    val.update(in_vals)
    for _ in range(max_pass):
        before = dict(val)
        for kind, ins, out in gates:
            vs = [val.get(n, 1) for n in ins]
            val[out] = _EVAL[kind](vs)
        for n, v in in_vals.items():
            val[n] = v
        if val == before:
            return True, val
    return False, val


def truth_table(name, outdir='.', inputs_order=None, outputs_order=None):
    """Enumerate every input combination of ``name.circ`` and print the
    settled outputs (with an unstable marker for non-converging rows).

    Returns the list of rows as ``(in_dict, out_dict, stable)``.
    """
    gates, inputs, outputs = netlist_from_circ(name, outdir)
    in_names = inputs_order or sorted(inputs)
    out_names = outputs_order or sorted(outputs)
    print(f"  {name}:  inputs {in_names}  ->  outputs {out_names}")
    print("  " + " ".join(in_names) + "  |  " + " ".join(out_names))
    rows = []
    for combo in itertools.product((0, 1), repeat=len(in_names)):
        forced = {inputs[n]: v for n, v in zip(in_names, combo)}
        stable, val = simulate(gates, forced)
        outs = {n: val[outputs[n]] for n in out_names}
        flag = "" if stable else "  (UNSTABLE/oscillates)"
        print("  " + " ".join(str(v) for v in combo) + "  |  "
              + " ".join(str(outs[n]) for n in out_names) + flag)
        rows.append((dict(zip(in_names, combo)), outs, stable))
    return rows


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
        print("usage: python -m logikit.sim [--dir=DIR] NAME [NAME ...]")
        return 2
    for n in names:
        truth_table(n, outdir)
    return 0


if __name__ == '__main__':
    sys.exit(main())
