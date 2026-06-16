#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Breadboard / DIP *wiring diagrams* (結線図) as clean vector PDF.

A schematic shows the logic; a wiring diagram shows what you actually patch on
the bench.  This module draws a power box (電源箱: GND/Vcc + a row of electrode
keys) above one or more logic boxes (論理箱: each a 14-pin DIP such as a
74LS00 quad-NAND), then routes every net as orthogonal black cables in the
style of a hand-drawn lab figure.

Pin layout (matches a standard 14-pin DIP / the lab guide)::

    top row  (left -> right):  7 6 5 4 3 2 1
    bottom   (left -> right): 14 13 12 11 10 9 8
    Vcc = pin 14,  GND = pin 7

Routing model: each net is a tree of orthogonal segments.  Signal nets get a
horizontal trunk on a dedicated track in the channel above the boxes (for
top-row pins / electrodes) and/or a track below (bottom-row pins), joined by a
side riser when a net spans both.  T-junctions get a solder dot; plain
crossings do not — standard schematic convention.  Power nets wrap over the
top-left corner.

Output: a standalone, auto-cropped PDF per scene.  Rendering needs ``lualatex``
with a CJK font (the box labels are Japanese by default; override
``logic_label`` / ``power_label`` for an all-Latin figure).
"""
from __future__ import annotations

import os
import subprocess

# ----------------------------------------------------------------------
# geometry (cm, y up)
# ----------------------------------------------------------------------
PITCH = 0.95               # horizontal pin spacing
PINR = 0.24                # pin / electrode circle radius
ICW = 1.30 + 6 * PITCH     # logic-box width (= 7.0)
ICH = 2.55                 # logic-box height
TOPY = ICH - 0.45          # top pin-row y
BOTY = 0.45                # bottom pin-row y
ICGAP = 1.9                # gap between logic boxes
PWRH = 2.35                # power-box height

RPAD = 1.25                # right padding inside logic box for its label
TRACK = 0.36               # spacing between routing tracks
SIDE = 0.42                # spacing between side risers


def pin_col(pin):
    """Column index (0 = leftmost .. 6 = rightmost) of a DIP pin."""
    return (7 - pin) if 1 <= pin <= 7 else (14 - pin)


class Scene:
    """One wiring figure: ``n_ic`` logic boxes and a power box, plus the nets.

    Build it by calling :meth:`net` / :meth:`gnd_net` / :meth:`vcc_net` to
    register connections (routing is deferred), then :meth:`layout` and
    :meth:`tikz`.  Terminals are addressed as:

    * ``('E', n)``      — electrode key ``n`` (1..7) on the power box, or
    * ``('P', k, pin)`` — pin ``pin`` (1..14) of logic box ``k`` (0-based).
    """

    def __init__(self, n_ic):
        self.n_ic = n_ic
        self.lines = []            # (x1, y1, x2, y2)
        self.dots = []             # (x, y)
        self.icx = [k * (ICW + ICGAP) for k in range(n_ic)]
        self.total_w = n_ic * ICW + (n_ic - 1) * ICGAP
        # power box, centred over the ICs, shifted +0.5 pitch (avoid pin alignment)
        self.pwr_w = ICW
        self.pwr_x0 = (self.total_w - self.pwr_w) / 2 + 0.5 * PITCH
        self._top_i = 0
        self._bot_j = 0
        self._sideR = 0
        self._sideL = 0
        self.pwr_b = ICH + 3.4     # finalised in layout()
        # captions / labels
        self.elec_labels = {}      # electrode n -> text above the key
        self.ic_name = "74LS00N"   # DIP part number drawn in each logic box
        self.ic_tags = {}          # box k -> short tag, e.g. "IC1"
        self.logic_label = "論理箱"
        self.power_label = "電源箱"
        self.pending = []          # registered nets, routed in layout()

    # ---- track / side allocators -------------------------------------
    def top_track(self):
        y = ICH + 0.55 + self._top_i * TRACK
        self._top_i += 1
        return y

    def bot_track(self):
        y = -0.55 - self._bot_j * TRACK
        self._bot_j += 1
        return y

    def side_right(self):
        x = self.total_w + RPAD + 0.7 + self._sideR * SIDE
        self._sideR += 1
        return x

    def side_left(self):
        x = -0.7 - self._sideL * SIDE
        self._sideL += 1
        return x

    # ---- primitives ---------------------------------------------------
    def seg(self, x1, y1, x2, y2):
        self.lines.append((round(x1, 3), round(y1, 3), round(x2, 3), round(y2, 3)))

    def dot(self, x, y):
        self.dots.append((round(x, 3), round(y, 3)))

    # ---- coordinate resolution ---------------------------------------
    def elec_x(self, n):
        return self.pwr_x0 + 0.65 + (7 - n) * PITCH

    @property
    def elec_y(self):
        return self.pwr_b + 0.62

    @property
    def gv_y(self):
        return self.pwr_b + PWRH - 0.62

    def gnd_xy(self):
        return (self.pwr_x0 + 0.95, self.gv_y)

    def vcc_xy(self):
        return (self.pwr_x0 + 1.95, self.gv_y)

    def resolve(self, term):
        """-> dict(x, ya, region); ``ya`` is the wire attach point (circle edge)."""
        t = term[0]
        if t == 'E':
            n = term[1]
            return dict(x=self.elec_x(n), ya=self.elec_y - PINR, region='top')
        if t == 'P':
            k, pin = term[1], term[2]
            x = self.icx[k] + 0.65 + pin_col(pin) * PITCH
            if 1 <= pin <= 7:
                return dict(x=x, ya=TOPY + PINR, region='top')
            return dict(x=x, ya=BOTY - PINR, region='bot')
        raise ValueError(term)

    # ---- one horizontal trunk with vertical drops --------------------
    def trunk(self, yt, terms, extra_x=None):
        xs = [t['x'] for t in terms]
        allx = xs + ([extra_x] if extra_x is not None else [])
        x0, x1 = min(allx), max(allx)
        self.seg(x0, yt, x1, yt)
        for t in terms:
            self.seg(t['x'], t['ya'], t['x'], yt)
            if x0 < t['x'] < x1:
                self.dot(t['x'], yt)
        if extra_x is not None and x0 < extra_x < x1:
            self.dot(extra_x, yt)
        return x0, x1

    # ---- net registration (routing deferred until layout) ------------
    def net(self, terminals, side='R'):
        """Register a signal net joining ``terminals`` (a list of E/P tuples).

        ``side`` ('R' or 'L') chooses which side risers run on when the net
        spans both the top and bottom pin rows.
        """
        self.pending.append(('sig', terminals, side))

    def gnd_net(self):
        """Wire pin 7 (GND) of every logic box to the power box's GND."""
        self.pending.append(('gnd',))

    def vcc_net(self):
        """Wire pin 14 (Vcc) of every logic box to the power box's Vcc."""
        self.pending.append(('vcc',))

    # ---- routing ------------------------------------------------------
    def _route_sig(self, terminals, side):
        terms = [self.resolve(t) for t in terminals]
        top = [t for t in terms if t['region'] == 'top']
        bot = [t for t in terms if t['region'] == 'bot']
        if top and bot:
            sx = self.side_right() if side == 'R' else self.side_left()
            yt = self.top_track()
            yb = self.bot_track()
            self.trunk(yt, top, extra_x=sx)
            self.trunk(yb, bot, extra_x=sx)
            self.seg(sx, yt, sx, yb)
        elif top:
            self.trunk(self.top_track(), top)
        else:
            self.trunk(self.bot_track(), bot)

    def _route_gnd(self):
        gx, gy = self.gnd_xy()
        p7 = [self.resolve(('P', k, 7)) for k in range(self.n_ic)]
        yt = self.top_track()
        lx = self.side_left()
        wy = self.pwr_b + PWRH + 0.5
        self.seg(gx, gy + PINR, gx, wy)
        self.seg(gx, wy, lx, wy)
        self.seg(lx, wy, lx, yt)
        self.trunk(yt, p7, extra_x=lx)

    def _route_vcc(self):
        vx, vy = self.vcc_xy()
        p14 = [self.resolve(('P', k, 14)) for k in range(self.n_ic)]
        yb = self.bot_track()
        lx = self.side_left()
        wy = self.pwr_b + PWRH + 0.85
        self.seg(vx, vy + PINR, vx, wy)
        self.seg(vx, wy, lx, wy)
        self.seg(lx, wy, lx, yb)
        self.trunk(yb, p14, extra_x=lx)

    def layout(self):
        """Finalise geometry, then route every registered net.

        The power box must sit above the highest top track, but the number of
        top tracks is only known after the nets are examined.  Region
        (top/bottom) classification is independent of ``pwr_b``, so we count
        the top tracks first, fix ``pwr_b``, then route."""
        n_top = 0
        for item in self.pending:
            if item[0] == 'sig':
                terms = [self.resolve(t) for t in item[1]]
                if any(t['region'] == 'top' for t in terms):
                    n_top += 1
            elif item[0] == 'gnd':
                n_top += 1
        self.pwr_b = ICH + 0.55 + max(n_top, 1) * TRACK + 1.0
        self._top_i = self._bot_j = self._sideR = self._sideL = 0
        for item in self.pending:
            if item[0] == 'sig':
                self._route_sig(item[1], item[2])
            elif item[0] == 'gnd':
                self._route_gnd()
            elif item[0] == 'vcc':
                self._route_vcc()
        return self

    # ---- emit TikZ ----------------------------------------------------
    def tikz(self):
        out = []
        A = out.append
        # white box fills first (so stubs draw over edges, pins on top)
        for k in range(self.n_ic):
            x0 = self.icx[k]
            A(rf"\fill[white] ({x0:.3f},0) rectangle ({x0+ICW+RPAD:.3f},{ICH:.3f});")
        A(rf"\fill[white] ({self.pwr_x0:.3f},{self.pwr_b:.3f}) "
          rf"rectangle ({self.pwr_x0+self.pwr_w:.3f},{self.pwr_b+PWRH:.3f});")
        # wires
        for (x1, y1, x2, y2) in self.lines:
            A(rf"\draw[black,line width=0.5pt] ({x1},{y1})--({x2},{y2});")
        for (x, y) in self.dots:
            A(rf"\fill[black] ({x},{y}) circle (1.7pt);")
        # logic boxes
        for k in range(self.n_ic):
            x0 = self.icx[k]
            A(rf"\draw[black,line width=0.8pt] ({x0:.3f},0) "
              rf"rectangle ({x0+ICW+RPAD:.3f},{ICH:.3f});")
            for pin in range(1, 15):
                px = x0 + 0.65 + pin_col(pin) * PITCH
                py = TOPY if 1 <= pin <= 7 else BOTY
                A(rf"\node[draw,circle,line width=0.5pt,fill=white,inner sep=0pt,"
                  rf"minimum size={2*PINR}cm] at ({px:.3f},{py:.3f}) {{\footnotesize {pin}}};")
            cx, cy = x0 + ICW / 2, ICH / 2
            A(rf"\draw[black,line width=0.5pt] ({cx-0.95:.3f},{cy-0.27:.3f}) "
              rf"rectangle ({cx+0.95:.3f},{cy+0.27:.3f});")
            A(rf"\node at ({cx:.3f},{cy:.3f}) {{\footnotesize {self.ic_name}}};")
            tag = self.ic_tags.get(k, "")
            if tag:
                A(rf"\node[anchor=west] at ({x0+0.18:.3f},{cy:.3f}) {{\footnotesize {tag}}};")
            A(rf"\node[anchor=east,align=center] at ({x0+ICW+RPAD-0.13:.3f},{cy:.3f}) "
              rf"{{\footnotesize {self.logic_label}}};")
        # power box
        px0, pb = self.pwr_x0, self.pwr_b
        A(rf"\draw[black,line width=0.8pt] ({px0:.3f},{pb:.3f}) "
          rf"rectangle ({px0+self.pwr_w:.3f},{pb+PWRH:.3f});")
        for n in range(1, 8):
            ex = self.elec_x(n)
            A(rf"\node[draw,circle,line width=0.5pt,fill=white,inner sep=0pt,"
              rf"minimum size={2*PINR}cm] at ({ex:.3f},{self.elec_y:.3f}) {{\footnotesize {n}}};")
            if n in self.elec_labels:
                A(rf"\node[anchor=south] at ({ex:.3f},{self.elec_y+PINR+0.04:.3f}) "
                  rf"{{\footnotesize {self.elec_labels[n]}}};")
        gx, gy = self.gnd_xy()
        vx, vy = self.vcc_xy()
        for (cx, cy, lab) in [(gx, gy, "GND"), (vx, vy, "Vcc")]:
            A(rf"\node[draw,circle,line width=0.5pt,fill=white,inner sep=0pt,"
              rf"minimum size={2*PINR}cm] at ({cx:.3f},{cy:.3f}) {{}};")
            A(rf"\node[anchor=north,font=\scriptsize] at ({cx:.3f},{cy-PINR-0.02:.3f}) {{{lab}}};")
        A(rf"\node[anchor=east] at ({px0+self.pwr_w-0.15:.3f},{pb+PWRH-0.32:.3f}) "
          rf"{{\footnotesize {self.power_label}}};")
        return "\n".join(out)


# Standalone LuaLaTeX document.  Uses luatexja-fontspec with Harano Aji fonts so
# the Japanese box labels render; for an all-Latin figure (logic_label /
# power_label set to ASCII) any engine with tikz works, but lualatex is assumed.
DOC = r"""\documentclass[border=5pt]{standalone}
\usepackage{luatexja-fontspec}
\setmainjfont{HaranoAjiMincho}
\setsansjfont{HaranoAjiGothic}
\usepackage{tikz}
\begin{document}
\begin{tikzpicture}[line cap=round, line join=round]
%s
\end{tikzpicture}
\end{document}
"""


def render_scene(scene, name, outdir='build', doc=DOC, keep_aux=False):
    """Lay out ``scene``, compile it with ``lualatex`` and return the PDF path.

    Writes ``outdir/name.tex`` and ``outdir/name.pdf``.  Raises
    ``RuntimeError`` (with the tail of the LaTeX log) if compilation fails.
    """
    os.makedirs(outdir, exist_ok=True)
    scene.layout()
    tex = doc % scene.tikz()
    texpath = os.path.join(outdir, name + '.tex')
    with open(texpath, 'w') as f:
        f.write(tex)
    r = subprocess.run(
        ['lualatex', '-interaction=nonstopmode', '-halt-on-error', name + '.tex'],
        cwd=outdir, capture_output=True, text=True)
    pdf = os.path.join(outdir, name + '.pdf')
    if r.returncode != 0 or not os.path.exists(pdf):
        raise RuntimeError(f"lualatex failed for {name}:\n" + r.stdout[-2500:])
    if not keep_aux:
        for ext in ('.aux', '.log'):
            p = os.path.join(outdir, name + ext)
            if os.path.exists(p):
                os.remove(p)
    print(f"[ok] {name} -> {pdf}")
    return pdf
