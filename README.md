# logikit

Generate, render and **verify** digital-logic figures from Python — gate
schematics (as real-wire Logisim `.circ` → PNG) and breadboard / DIP wiring
diagrams (結線図, as vector PDF) — without drawing anything by hand.

It grew out of writing up a digital-logic lab, where I needed dozens of NAND
schematics and 74-series breadboard diagrams that were **correct** and looked
consistent. Hand-drawing them is slow and error-prone; this makes them
reproducible and machine-checkable.

<p align="center">
  <img src="docs/mux2_nand.png" width="78%" alt="2:1 multiplexer schematic"><br>
  <em>A 2:1 multiplexer from 1 NOT + 3 NANDs — generated, connectivity-checked,
  and rendered by logikit (see <code>examples/</code>).</em>
</p>

## Why

Most `.circ` generators connect gates with *tunnels* (named virtual links), so
the file simulates but the rendered picture looks nothing like a schematic.
`logikit` lays out **real orthogonal wires**, so the rendered figure is a
genuine gate-and-wire diagram — junction dots, crossings and all — and a
static checker proves the wiring matches what you intended before you trust it.

## What's in the box

| Capability | Module / file | Output |
|---|---|---|
| Build a schematic from a tiny Python DSL (real wires) | `logikit/circ.py` | `name.circ`, `name_fig.circ`, `name.spec` |
| **Statically verify** connectivity (catch shorts & opens) | `logikit/check.py` | pass/fail report |
| Simulate the netlist (truth tables, **oscillation detection**) | `logikit/sim.py` | truth table |
| Render a `.circ` to PNG using Logisim's own drawing code | `render/LogiRender.java` + `render/render.sh` | `name.png` |
| Breadboard / DIP wiring diagrams (結線図) | `logikit/wiring.py` | `name.pdf` |

The Python package is **pure standard library** — no `pip install` of
dependencies needed to generate, check and simulate. Rendering needs a JDK +
the Logisim jar (PNG) and/or `lualatex` (breadboard PDF).

## Requirements

- **Python ≥ 3.9** (generation / check / simulation — stdlib only).
- **A JDK** and **[Logisim-evolution](https://github.com/logisim-evolution/logisim-evolution)**'s
  `…-all.jar` for PNG rendering. Point `LOGISIM_JAR` at it (the jar is **not**
  bundled here — it's ~50 MB and third-party). On macOS the renderer also
  auto-detects `/Applications/Logisim-evolution.app/...`.
- **`lualatex`** + a CJK font (e.g. Harano Aji, shipped with TeX Live) for the
  breadboard PDFs, whose box labels are Japanese by default. For an all-Latin
  figure, set `scene.logic_label` / `scene.power_label` to ASCII.

## Quickstart

```bash
git clone https://github.com/taitaitai58/logikit
cd logikit

# 1. generate the example schematics, then check + simulate them
python3 -m examples.circuits
#   -> build/{mux2_nand,and3_nand,ring_osc_nand}{,_fig}.circ + .spec
#   -> connectivity report (all OK) + truth tables (ring oscillator: UNSTABLE)

# 2. render a clean PNG (uses Logisim's own draw code)
export LOGISIM_JAR=/path/to/logisim-evolution-X.Y.Z-all.jar
./render/render.sh build/mux2_nand_fig.circ build/mux2_nand.png 4

# 3. build the breadboard wiring diagram (needs lualatex + a CJK font)
python3 -m examples.breadboard
#   -> build/wiring_mux2.pdf
```

## Writing your own circuit

A circuit is just a function `fn(c)` that places gates and routes wires. Open
the file in Logisim afterwards, or render the `_fig` variant to PNG.

```python
from logikit.circ import emit
from logikit.check import check
from logikit.sim import truth_table

def half_nand(c):
    A  = c.pin_in(90, 100, 'A')
    B  = c.pin_in(90, 260, 'B')
    g  = c.nand(360, 180)              # NAND gate, output at (360,180)
    Yo = c.pin_out(520, 180, 'Y')      # Y = NOT(A AND B)
    c.fan(A, 200, [g['in'][0]], net='A')
    c.fan(B, 180, [g['in'][1]], net='B')
    c.path(g['out'], Yo)
    c.mark('Y', g['out'])

emit('half_nand', half_nand, 'build')  # writes build/half_nand{,_fig}.circ + .spec
check('half_nand', 'build')            # static connectivity check
truth_table('half_nand', 'build')      # 2x2 truth table
```

### The DSL

`Circ` (in `logikit/circ.py`) gives you:

- `pin_in(x, y, label)` / `pin_out(x, y, label)` — I/O terminals.
- `gate(x, y, kind, n)` — a 2- or 3-input `NAND`/`AND`/`OR`/`NOR`/`XOR`/`XNOR`;
  `nand(...)` and `notg(...)` are shortcuts.
- `nand_inv(x, y)` — an inverter from a NAND with its inputs tied (the standard
  quad-NAND trick); returns the physical `pins` to annotate.
- `w(p, q)` / `path(*pts)` — axis-aligned wires.
- `fan(driver, trunk_x, [receivers], net=...)` — route one source up a vertical
  trunk and out to several receivers.
- `mark(net, *ports)` — declare the *intended* net of some ports, which
  `logikit.check` verifies against the actual geometry.

**Geometry** (Logisim `size=50`, grid 10, gates face East): a gate's output is
at `(x, y)`; its 2 inputs at `(x-50, y-20)` and `(x-50, y+20)` (a 3rd input adds
the centre `(x-50, y)`); a `NOT` is width 30 so its input is `(x-30, y)`.
Connectivity is by geometry, exactly like Logisim: wires sharing an endpoint or
meeting at a T-junction are one net; pure crossings are **not** connected.

### Breadboard diagrams

`Scene` (in `logikit/wiring.py`) draws one or more 14-pin DIP "logic boxes" and
a "power box", and routes nets addressed by `('E', n)` (electrode key) or
`('P', k, pin)` (pin of box `k`). See `examples/breadboard.py`.

## Use it from an AI agent

This repo ships a [Claude Code](https://claude.com/claude-code) **skill** at
[`.claude/skills/logisim-figures/SKILL.md`](.claude/skills/logisim-figures/SKILL.md).
Open the repo in Claude Code and the agent can drive the whole
generate → check → render loop for you ("draw me a NAND SR latch and verify it").

## Project layout

```
logikit/
├── logikit/            # pure-stdlib package: circ, check, sim, wiring
├── render/             # LogiRender.java + render.sh (headless .circ -> PNG)
├── examples/           # mux2 / and3 / ring oscillator + a 74LS00 breadboard
├── .claude/skills/     # the logisim-figures AI skill
└── docs/               # rendered example images for this README
```

## A note on scope

This toolkit is the *engine* only. The example circuits here (a MUX, a 3-input
AND, a ring oscillator) are generic building blocks included to demonstrate the
features — **no specific course-assignment circuits or report content are
included.**

## 日本語

論理回路の図（NAND 等のゲート回路図と、74 シリーズ DIP のブレッドボード結線図）を
Python から生成・**検証**・描画するツールキットです。`.circ` を実配線（トンネルを
使わない）で生成 → 接続関係を静的チェック（ショート/断線を検出）→ Logisim 自身の
描画で PNG 化、さらに結線図を TikZ/LuaLaTeX で PDF 化します。Python 部分は標準
ライブラリのみ。詳しい使い方は上記 Quickstart と `examples/` を参照してください。

## License

[MIT](LICENSE)
