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

Routing model — **point-to-point only, no branched cables**.  Real jumper
wires have exactly two ends, so a reproducible wiring diagram must use only
two-terminal cables: a single cable may never branch (no T-junction / solder
dot mid-wire).  A net that joins *k* terminals is therefore wired as a **star**
fanning out from its *source* terminal (the 極 — the first terminal passed to
:meth:`net`; for an input net that is the electrode key, for an internal net
the driving gate-output pin).  One independent orthogonal cable runs from that
hub to each of the other terminals.  The hub (an electrode key or a DIP pin /
breadboard column) physically takes several wire-ends, so the cables fan out
from it at small offsets; every other terminal receives exactly one cable.
Each cable runs on its own track in the channel above the boxes (top-row pins /
electrodes) and/or below (bottom-row pins), joined by a side riser when it
spans both rows.  Power nets fan the same way from the GND / Vcc terminal.
There are **no solder dots**: every junction sits on a terminal, never on a
free cable.

Output: a standalone, auto-cropped PDF per scene.  Rendering needs ``lualatex``
with a CJK font (the box labels are Japanese by default; override
``logic_label`` / ``power_label`` for an all-Latin figure).
"""
from __future__ import annotations

import os
import shutil
import subprocess

from . import _env

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
LAND = 0.17                # max |x-offset| of a fanned cable's landing (< PINR,
                           # so every cable end lands inside its terminal circle)
GAP = 0.05                 # innermost landing offset when a hub fans to both sides


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

    The **first** terminal of a :meth:`net` is its source (極 / hub): every
    other terminal is wired to it by an independent point-to-point cable.
    """

    def __init__(self, n_ic):
        self.n_ic = n_ic
        self.lines = []            # (x1, y1, x2, y2) — flattened, for TikZ
        self.cables = []           # {a, b, segs} per point-to-point cable
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

    def _poly(self, pts):
        """Emit an orthogonal polyline (one cable); return its rounded segments."""
        segs = []
        for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
            if (round(x1, 3), round(y1, 3)) == (round(x2, 3), round(y2, 3)):
                continue                                  # skip zero-length
            self.seg(x1, y1, x2, y2)
            segs.append((round(x1, 3), round(y1, 3), round(x2, 3), round(y2, 3)))
        return segs

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

    def _region(self, term):
        """'top' (electrodes + pins 1-7) or 'bot' (pins 8-14) — no pwr_b needed."""
        if term[0] == 'E':
            return 'top'
        if term[0] == 'P':
            return 'top' if 1 <= term[2] <= 7 else 'bot'
        raise ValueError(term)

    def resolve(self, term):
        """-> dict(x, cy, ya, region).

        ``cy`` is the terminal-circle centre; cables land THERE (inside the
        radius) so the pin/electrode circle — drawn last, on top — cleanly caps
        the wire end.  ``ya`` is the circle edge (kept for reference)."""
        t = term[0]
        if t == 'E':
            cx, cy = self.elec_x(term[1]), self.elec_y
            return dict(x=cx, cy=cy, ya=cy - PINR, region='top')
        if t == 'P':
            k, pin = term[1], term[2]
            cx = self.icx[k] + 0.65 + pin_col(pin) * PITCH
            if 1 <= pin <= 7:
                return dict(x=cx, cy=TOPY, ya=TOPY + PINR, region='top')
            return dict(x=cx, cy=BOTY, ya=BOTY - PINR, region='bot')
        raise ValueError(term)

    # ---- net registration (routing deferred until layout) ------------
    def net(self, terminals, side='R'):
        """Register a signal net joining ``terminals`` (a list of E/P tuples).

        ``terminals[0]`` is the source (極 / hub): the net is wired as a star
        of point-to-point cables, one from the hub to each other terminal.
        ``side`` ('R' or 'L') chooses which side risers a cable uses when it
        spans both the top and bottom pin rows.
        """
        self.pending.append(('sig', terminals, side))

    def gnd_net(self):
        """Wire pin 7 (GND) of every logic box to the power box's GND."""
        self.pending.append(('gnd',))

    def vcc_net(self):
        """Wire pin 14 (Vcc) of every logic box to the power box's Vcc."""
        self.pending.append(('vcc',))

    # ---- routing: one point-to-point cable ---------------------------
    def _cable(self, hub_t, hub, off, tgt_t, tgt, side):
        """Draw one two-terminal cable from the hub (landing offset ``off``) to a
        target.  Both ends land at the terminal-circle centre (``cy``), so the
        circle drawn on top caps the wire end inside its radius."""
        hx, hy, hr = hub['x'] + off, hub['cy'], hub['region']
        tx, ty = tgt['x'], tgt['cy']
        if tgt['region'] == hr:                           # same row -> one track
            yc = self.top_track() if hr == 'top' else self.bot_track()
            pts = [(hx, hy), (hx, yc), (tx, yc), (tx, ty)]
        else:                                             # spans rows -> side riser
            sx = self.side_right() if side == 'R' else self.side_left()
            if hr == 'top':
                yh, yo = self.top_track(), self.bot_track()
            else:
                yh, yo = self.bot_track(), self.top_track()
            pts = [(hx, hy), (hx, yh), (sx, yh), (sx, yo), (tx, yo), (tx, ty)]
        self.cables.append({'a': hub_t, 'b': tgt_t, 'segs': self._poly(pts)})

    def _route_star(self, terminals, side):
        """Fan independent cables from the source terminal to every other one.

        Cables leave the hub at distinct landing offsets, all within ``LAND`` of
        the centre so each end stays inside the hub circle.  Within a side the
        nearest target gets the outermost landing + lowest track (nested, so the
        same-net cables do not cross); a hub that fans to one side only spreads
        its cables across the full circle, otherwise each side keeps to its half."""
        hub_t = terminals[0]
        hub = self.resolve(hub_t)
        seen = set()
        tgts = [t for t in terminals[1:]                  # drop the hub + duplicates
                if t != hub_t and not (t in seen or seen.add(t))]
        if not tgts:
            return
        if len(tgts) == 1:                                # clean centred cable
            self._cable(hub_t, hub, 0.0, tgts[0], self.resolve(tgts[0]), side)
            return
        # split targets left/right of the hub; spans go to the chosen side
        left, right = [], []
        for tg in tgts:
            tr = self.resolve(tg)
            if tr['region'] != hub['region']:             # spanning cable
                go_right, reach = (side == 'R'), float('inf')
            else:
                go_right, reach = (tr['x'] >= hub['x']), abs(tr['x'] - hub['x'])
            (right if go_right else left).append((reach, tg, tr))
        both = bool(left) and bool(right)
        for grp, sgn in ((right, +1.0), (left, -1.0)):
            if not grp:
                continue
            grp.sort(key=lambda e: e[0])                  # nearest first
            k = len(grp)
            # nearest -> outermost landing (toward this side); farthest -> inner.
            # one-sided hub uses the whole circle [-LAND, +LAND]; two-sided keeps
            # to its half [GAP, LAND].
            outer, inner = sgn * LAND, (sgn * GAP if both else -sgn * LAND)
            for idx, (reach, tg, tr) in enumerate(grp):
                off = outer if k == 1 else outer + (inner - outer) * idx / (k - 1)
                self._cable(hub_t, hub, off, tg, tr, side)

    # ---- power nets (Vcc / GND): a star from the power terminal -------
    def _route_gnd(self):
        gx, gy = self.gnd_xy()                            # gy = GND-circle centre
        m = self.n_ic
        step = min(LAND / max(m, 1), 0.10)                # keep landings inside the circle
        for k in range(m):
            p7 = self.resolve(('P', k, 7))
            yt = self.top_track()
            lx = self.side_left()
            wy = self.pwr_b + PWRH + 0.5 + k * 0.30
            gxx = gx + (k - (m - 1) / 2) * step
            pts = [(gxx, gy), (gxx, wy), (lx, wy), (lx, yt),
                   (p7['x'], yt), (p7['x'], p7['cy'])]
            self.cables.append({'a': ('GND',), 'b': ('P', k, 7), 'segs': self._poly(pts)})

    def _route_vcc(self):
        vx, vy = self.vcc_xy()                            # vy = Vcc-circle centre
        m = self.n_ic
        step = min(LAND / max(m, 1), 0.10)
        for k in range(m):
            p14 = self.resolve(('P', k, 14))
            yb = self.bot_track()
            lx = self.side_left()
            wy = self.pwr_b + PWRH + 0.85 + k * 0.30
            vxx = vx + (k - (m - 1) / 2) * step
            pts = [(vxx, vy), (vxx, wy), (lx, wy), (lx, yb),
                   (p14['x'], yb), (p14['x'], p14['cy'])]
            self.cables.append({'a': ('VCC',), 'b': ('P', k, 14), 'segs': self._poly(pts)})

    def layout(self):
        """Finalise geometry, then route every registered net as point-to-point cables.

        The power box must sit above the highest top track, but the number of
        top tracks is only known after the nets are examined.  Region
        (top/bottom) classification is independent of ``pwr_b``, so we count
        the top tracks first, fix ``pwr_b``, then route."""
        n_top = 0
        for item in self.pending:
            if item[0] == 'sig':
                hr = self._region(item[1][0])
                for tg in item[1][1:]:
                    tr = self._region(tg)
                    if hr == 'top' and tr == 'top':
                        n_top += 1
                    elif hr == 'bot' and tr == 'bot':
                        pass
                    else:                                 # spanning cable -> a top track
                        n_top += 1
            elif item[0] == 'gnd':
                n_top += self.n_ic                        # one top cable per IC
        self.pwr_b = ICH + 0.55 + max(n_top, 1) * TRACK + 1.0
        self._top_i = self._bot_j = self._sideR = self._sideL = 0
        for item in self.pending:
            if item[0] == 'sig':
                self._route_star(item[1], item[2])
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
        # wires (point-to-point cables; no solder dots — nothing branches)
        for (x1, y1, x2, y2) in self.lines:
            A(rf"\draw[black,line width=0.5pt] ({x1},{y1})--({x2},{y2});")
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
# the Japanese box labels (論理箱 / 電源箱) render.
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

# All-Latin variant: plain tikz, no CJK font required.  Use this together with
# ASCII labels (scene.logic_label / power_label) when you don't have a CJK font.
DOC_LATIN = r"""\documentclass[border=5pt]{standalone}
\usepackage{tikz}
\begin{document}
\begin{tikzpicture}[line cap=round, line join=round]
%s
\end{tikzpicture}
\end{document}
"""


def _looks_like_font_error(log):
    low = log.lower()
    return (('haranoaji' in low or 'fontspec' in low or 'luaotfload' in low
             or 'luatexja' in low)
            and ('not found' in low or 'cannot' in low or 'could not' in low
                 or 'unable to' in low or 'fatal' in low))


def render_scene(scene, name, outdir='build', doc=DOC, keep_aux=False):
    """Lay out ``scene``, compile it with ``lualatex`` and return the PDF path.

    Writes ``outdir/name.tex`` and ``outdir/name.pdf``.  Raises a
    ``RuntimeError`` with an actionable message if ``lualatex`` is missing or
    compilation fails (a missing CJK font gets a targeted hint).
    """
    if shutil.which('lualatex') is None:
        raise RuntimeError(
            "`lualatex` was not found on PATH, so the breadboard PDF cannot be "
            "built.\n" + _env.hint_lualatex() +
            "\n(The .circ generation / check / simulation parts need none of this.)")

    os.makedirs(outdir, exist_ok=True)
    scene.layout()
    tex = doc % scene.tikz()
    texpath = os.path.join(outdir, name + '.tex')
    with open(texpath, 'w') as f:
        f.write(tex)
    try:
        r = subprocess.run(
            ['lualatex', '-interaction=nonstopmode', '-halt-on-error', name + '.tex'],
            cwd=outdir, capture_output=True, text=True)
    except OSError as e:                       # e.g. lualatex vanished mid-run
        raise RuntimeError(f"could not run lualatex: {e}\n" + _env.hint_lualatex())

    pdf = os.path.join(outdir, name + '.pdf')
    if r.returncode != 0 or not os.path.exists(pdf):
        msg = [f"lualatex failed for {name!r}."]
        if doc is DOC and _looks_like_font_error(r.stdout):
            msg.append("\nThis looks like a missing CJK font:\n" + _env.hint_cjk_font())
        msg.append("\n--- lualatex log (tail) ---\n" + r.stdout[-2500:])
        raise RuntimeError("\n".join(msg))

    if not keep_aux:
        for ext in ('.aux', '.log'):
            p = os.path.join(outdir, name + ext)
            if os.path.exists(p):
                os.remove(p)
    print(f"[ok] {name} -> {pdf}")
    return pdf
