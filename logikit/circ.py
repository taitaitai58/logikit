#!/usr/bin/env python3
"""Build Logisim-evolution ``.circ`` files from Python, using REAL WIRES.

Most ``.circ`` generators cheat with *tunnels* (named virtual links), so the
result simulates but looks nothing like a hand-drawn schematic.  ``logikit``
instead lays out real orthogonal wires, so the rendered figure is a genuine
gate-and-wire diagram — junction dots, crossings and all.

Verified geometry (Logisim gate ``size=50``, grid 10, every gate faces East)::

    NAND/AND/OR/NOR  output port at (x, y)
                     2 inputs at (x-50, y-20) and (x-50, y+20)
                     3 inputs add a centre input at (x-50, y)
    NOT (width 30)   output (x, y), input (x-30, y)
    Pin (in or out)  port at (x, y)

Connectivity is decided purely by wire geometry, exactly like Logisim itself:
two wires that share an endpoint — or where one wire's endpoint lands on the
interior of another (a T-junction) — are the same net; wires that merely cross
are *not* connected.  Keep each net a connected tree of axis-aligned segments
and avoid dropping one net's endpoint onto another net's wire.

Each builder is just a function ``fn(c)`` that calls these methods.  Run a
builder through :func:`emit` to get three files:

* ``name.circ``      — input/output ``Pin``s, simulatable, opens cleanly in the
                       Logisim GUI.
* ``name_fig.circ``  — ``Text`` labels instead of ``Pin``s, for a clean figure
                       (render *this* variant to PNG with ``LogiRender``).
* ``name.spec``      — the intended port -> net map, consumed by
                       :mod:`logikit.check` to statically verify the wiring.
"""
from __future__ import annotations

import json
import os

HEADER = '''<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<project source="4.1.0" version="1.0">
  <lib desc="#Wiring" name="0"/>
  <lib desc="#Gates" name="1"/>
  <lib desc="#Base" name="7"/>
  <main name="main"/>
  <circuit name="main">
    <a name="circuit" val="main"/>
'''
FOOTER = '''  </circuit>
</project>
'''

# Logisim component names for the gates in the #Gates library.
GATE = {'NAND': 'NAND Gate', 'AND': 'AND Gate', 'OR': 'OR Gate',
        'NOR': 'NOR Gate', 'XOR': 'XOR Gate', 'XNOR': 'XNOR Gate'}


class Circ:
    """A single Logisim ``main`` circuit being built up part by part.

    ``mode='pin'`` emits real input/output ``Pin`` terminals (simulatable);
    ``mode='label'`` emits ``Text`` labels in their place (a clean figure with
    no dangling pins).  Build the same ``fn(c)`` in both modes — see
    :func:`emit`.
    """

    def __init__(self, mode: str = 'pin'):
        self.parts: list[str] = []
        self.mode = mode               # 'pin' (simulatable) or 'label' (figure)
        self.netof: dict[tuple, str] = {}   # port (x,y) -> intended net name

    # ---- intended-net annotations (consumed by logikit.check) ----------
    def mark(self, net, *ports):
        """Record that every ``port`` is intended to be on net ``net``."""
        for p in ports:
            self.netof[tuple(p)] = net

    # ---- I/O terminals -------------------------------------------------
    def pin_in(self, x, y, label):
        if self.mode == 'pin':
            self.parts.append(
                f'    <comp lib="0" loc="({x},{y})" name="Pin">'
                f'<a name="label" val="{label}"/></comp>')
        else:
            self.parts.append(
                f'    <comp lib="7" loc="({x - 10},{y})" name="Text">'
                f'<a name="text" val="{label}"/><a name="halign" val="right"/></comp>')
        self.netof[(x, y)] = label
        return (x, y)

    def pin_out(self, x, y, label):
        if self.mode == 'pin':
            self.parts.append(
                f'    <comp lib="0" loc="({x},{y})" name="Pin">'
                f'<a name="output" val="true"/>'
                f'<a name="label" val="{label}"/></comp>')
        else:
            self.parts.append(
                f'    <comp lib="7" loc="({x + 12},{y})" name="Text">'
                f'<a name="text" val="{label}"/><a name="halign" val="left"/></comp>')
        self.netof[(x, y)] = label
        return (x, y)

    # ---- gates ---------------------------------------------------------
    def gate(self, x, y, kind='NAND', n=2, label=None, xor='one'):
        """A 2- or 3-input logic gate facing East.

        ``kind`` is one of :data:`GATE` (NAND/AND/OR/NOR/XOR/XNOR).  Returns
        ``{'out': (x, y), 'in': [(..), (..)]}``.  Port geometry is verified for
        NAND/AND/OR/NOR; XOR/XNOR share the same port grid in Logisim but their
        left edge is drawn slightly differently.

        For XOR/XNOR, ``xor`` picks the multi-input behaviour (it is irrelevant
        for 2 inputs): ``'one'`` is Logisim's default ("exactly one input high")
        and ``'odd'`` emits ``<a name="xor" val="odd"/>`` for true odd-parity
        XOR.  :mod:`logikit.sim` reads this attribute, so simulation matches the
        rendered circuit either way.
        """
        if kind not in GATE:
            raise ValueError(f"unknown gate kind {kind!r}")
        lab = f'<a name="label" val="{label}"/>' if label else ''
        xa = ('<a name="xor" val="odd"/>'
              if kind in ('XOR', 'XNOR') and xor == 'odd' else '')
        self.parts.append(
            f'    <comp lib="1" loc="({x},{y})" name="{GATE[kind]}">'
            f'<a name="size" val="50"/><a name="inputs" val="{n}"/>{xa}{lab}</comp>')
        if n == 2:
            ins = [(x - 50, y - 20), (x - 50, y + 20)]
        elif n == 3:
            ins = [(x - 50, y - 20), (x - 50, y), (x - 50, y + 20)]
        else:
            raise ValueError(f"unsupported input count {n}")
        return {'out': (x, y), 'in': ins}

    def nand(self, x, y, n=2, label=None):
        """A NAND gate (the workhorse of NAND-only logic)."""
        return self.gate(x, y, 'NAND', n, label)

    def notg(self, x, y, label=None):
        """A dedicated NOT gate (width 30: input at ``(x-30, y)``)."""
        lab = f'<a name="label" val="{label}"/>' if label else ''
        self.parts.append(
            f'    <comp lib="1" loc="({x},{y})" name="NOT Gate">{lab}</comp>')
        return {'out': (x, y), 'in': [(x - 30, y)]}

    def nand_inv(self, x, y):
        """An inverter built from a 2-input NAND with its inputs tied together
        (``NAND(a, a) = not a``) — the standard trick when all you have is a
        quad-NAND chip.

        Returns ``out``, a single tie-node ``in`` for convenient routing, and
        ``pins`` = the two physical NAND inputs.  When annotating the net that
        drives this inverter, ``mark`` the ``pins`` (not the tie node), so the
        connectivity check sees the real component ports.
        """
        g = self.nand(x, y, 2)
        p1, p2 = g['in']                  # (x-50, y-20), (x-50, y+20)
        bx = x - 70                       # left bracket column
        self.w((bx, p1[1]), p1)           # bracket -> in1
        self.w((bx, p2[1]), p2)           # bracket -> in2
        self.w((bx, p1[1]), (bx, p2[1]))  # vertical tie
        return {'out': g['out'], 'in': [(bx, y)], 'pins': [p1, p2]}

    # ---- wires ---------------------------------------------------------
    def w(self, p1, p2):
        """A single axis-aligned wire segment."""
        (x1, y1), (x2, y2) = p1, p2
        assert x1 == x2 or y1 == y2, f"non-orthogonal {p1}->{p2}"
        if p1 != p2:
            self.parts.append(f'    <wire from="({x1},{y1})" to="({x2},{y2})"/>')

    def path(self, *pts):
        """A polyline of axis-aligned points: ``path(a, b, c)`` = a->b->c."""
        for a, b in zip(pts, pts[1:]):
            self.w(a, b)

    def fan(self, driver, trunkx, receivers, net=None):
        """Route a forward net from one ``driver`` (on the left) up a vertical
        trunk at ``trunkx`` and out to several ``receivers`` (on the right).

        Requires ``driver.x <= trunkx <= every receiver.x``.  If ``net`` is
        given, also annotates the driver and receivers as that intended net.
        """
        dx, dy = driver
        ys = [dy] + [r[1] for r in receivers]
        self.w((dx, dy), (trunkx, dy))
        self.w((trunkx, min(ys)), (trunkx, max(ys)))
        for (rx, ry) in receivers:
            self.w((trunkx, ry), (rx, ry))
        if net is not None:
            self.mark(net, driver, *receivers)

    # ---- output --------------------------------------------------------
    def write(self, path):
        with open(path, 'w') as f:
            f.write(HEADER + '\n'.join(self.parts) + '\n' + FOOTER)
        print("wrote", path)
        return path

    def write_spec(self, path):
        spec = {f"{x},{y}": net for (x, y), net in self.netof.items()}
        with open(path, 'w') as f:
            json.dump(spec, f, indent=0)
        print("wrote", path)
        return path


def emit(name, builder, outdir='.'):
    """Run ``builder(c)`` and write ``name.circ``, ``name.spec`` and
    ``name_fig.circ`` into ``outdir``.  Returns the three paths."""
    os.makedirs(outdir, exist_ok=True)
    base = os.path.join(outdir, name)

    cp = Circ('pin')
    builder(cp)
    circ = cp.write(base + '.circ')
    spec = cp.write_spec(base + '.spec')

    cf = Circ('label')
    builder(cf)
    fig = cf.write(base + '_fig.circ')
    return circ, spec, fig
