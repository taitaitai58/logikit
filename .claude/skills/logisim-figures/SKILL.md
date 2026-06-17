---
name: logisim-figures
description: >-
  Generate, render and verify digital-logic figures with the logikit toolkit:
  build real-wire Logisim .circ schematics from a small Python DSL, statically
  check their connectivity (shorts/opens), simulate them (truth tables,
  oscillation detection), render them to clean PNGs via Logisim's own draw code,
  and produce 74-series breadboard/DIP wiring diagrams (結線図) as vector PDF.
  Use this when asked to draw/build a gate schematic or NAND-logic circuit
  (XOR, adder, latch, flip-flop, mux, decoder, ...), turn a .circ into an image,
  verify a circuit's wiring, or make a breadboard wiring diagram for a report.
---

# logisim-figures

A toolkit for producing **correct, reproducible** digital-logic figures. The
core idea: lay out circuits with *real wires* (not tunnels), so the picture is a
genuine schematic, and **statically verify** the wiring before trusting it.

Work from the repo root. The Python package is pure stdlib (no install needed).

## The loop (do this every time)

1. **Write** a builder `fn(c)` that places gates and routes wires.
2. **Emit** → `emit('name', fn, 'build')` writes `name.circ` (simulatable),
   `name_fig.circ` (clean figure), and `name.spec` (intended nets).
3. **Check** → `check('name', 'build')`. If it reports `[SHORT]`, `[OPEN]` or
   `[MISS]`, **fix the geometry and regenerate** — do not proceed to render a
   circuit that failed the check.
4. **Simulate** → `truth_table('name', 'build')` to confirm behaviour (and to
   see oscillation for feedback circuits).
5. **Render** → `./render/render.sh build/name_fig.circ build/name.png 4`.

This generate → check → fix iteration is the whole point: it catches a
miswired figure that would otherwise look perfectly convincing.

## Minimal example

```python
import sys; sys.path.insert(0, '.')        # run from repo root
from logikit.circ import emit
from logikit.check import check
from logikit.sim import truth_table

def my_xor(c):
    A  = c.pin_in(90, 100, 'A')
    B  = c.pin_in(90, 320, 'B')
    g1 = c.nand(340, 200)
    g2 = c.nand(560, 120)
    g3 = c.nand(560, 300)
    X  = c.nand(780, 210)
    Xo = c.pin_out(900, 210, 'X')
    # ... route with c.fan / c.path / c.w, and c.mark each net ...

emit('my_xor', my_xor, 'build')
check('my_xor', 'build')        # must print OK
truth_table('my_xor', 'build')  # confirm the truth table
```

See `examples/circuits.py` for three complete, checked builders (a 2:1 mux, a
3-input AND, and a ring oscillator) — copy their structure.

## DSL reference (`logikit/circ.py`)

Build a `Circ` via the `fn(c)` builder. Methods:

- `c.pin_in(x, y, label)` / `c.pin_out(x, y, label)` — I/O terminals. Returns
  `(x, y)`.
- `c.gate(x, y, kind, n=2, label=None)` — a 2/3-input gate; `kind` ∈
  `NAND, AND, OR, NOR, XOR, XNOR`. Returns `{'out': (x,y), 'in': [..]}`.
- `c.nand(x, y, n=2)` / `c.notg(x, y)` — shortcuts.
- `c.nand_inv(x, y)` — inverter from a NAND with tied inputs. Returns
  `{'out', 'in': [tie_node], 'pins': [p1, p2]}`. When marking the net that
  drives it, use `*g['pins']` (the real ports), not the tie node.
- `c.w(p, q)` — one axis-aligned wire. `c.path(a, b, c, ...)` — a polyline.
- `c.fan(driver, trunk_x, [receivers], net='name')` — route `driver` (left) up a
  vertical trunk at `trunk_x` out to several receivers (right). Requires
  `driver.x ≤ trunk_x ≤ every receiver.x`. Also marks the net if `net=` given.
- `c.mark(net, *ports)` — declare intended net membership for the check.

### Geometry (memorise this)

Gates face **East**, `size=50`, grid 10:

- gate output port: `(x, y)`
- 2 inputs: `(x-50, y-20)` and `(x-50, y+20)`; a 3rd input adds `(x-50, y)`
- `NOT` is width 30: input at `(x-30, y)`
- a `Pin`'s port is at its `(x, y)`

**Connectivity is purely geometric**, exactly like Logisim: two wires sharing
an endpoint, or where one wire's endpoint lands on another's interior (a
T-junction), are the same net; two wires that merely *cross* are **not**
connected. So:

- Keep each net a connected tree of orthogonal segments.
- A wire crossing another net's wire is fine (no dot, not connected) — but never
  let one net's *endpoint* land on another net's wire (that shorts them).
- `c.mark` every port of every net; the check fails loudly if geometry and
  intent disagree.

## Verifying (`logikit/check.py`, `logikit/sim.py`)

- `check('name', 'build')` → prints `OK`/`FAIL`. `[SHORT]` = two nets merged,
  `[OPEN]` = one net split / floating port, `[MISS]` = a `mark`ed port isn't a
  real component port (often a `nand_inv` marked at the tie node instead of
  `pins`).
- `truth_table('name', 'build')` → enumerates inputs, prints settled outputs,
  flags rows that **oscillate** (no fixpoint). Feedback/latch circuits settle to
  a stable state; a ring oscillator reports `UNSTABLE`.
- CLI equivalents: `python3 -m logikit.check --dir=build NAME` and
  `python3 -m logikit.sim --dir=build NAME`.

## Rendering to PNG (`render/`)

```bash
export LOGISIM_JAR=/path/to/logisim-evolution-X.Y.Z-all.jar   # required
./render/render.sh build/NAME_fig.circ build/NAME.png 4        # scale 4
```

- Render the **`_fig` variant** (Text labels instead of Pins) for figures — the
  pin variant can show inputs as unknown `x` values.
- `render.sh` compiles `LogiRender.java` on first use and auto-detects the jar
  at the standard macOS app path if `LOGISIM_JAR` is unset.
- `LogiRender` uses Logisim's own `circ.draw(...)` (crisp black wires, junction
  dots, opaque shaped gate bodies) and calls `System.exit(0)` so it doesn't
  leave a hung JVM.

## Breadboard / DIP wiring diagrams (`logikit/wiring.py`)

For "結線図" (which IC pin connects to which) on 14-pin DIPs + a power box:

```python
import sys; sys.path.insert(0, '.')
from logikit.wiring import Scene, render_scene

def wiring(): 
    s = Scene(1)                       # one logic box (14-pin DIP)
    s.ic_tags = {0: "IC1"}
    s.elec_labels = {1: "$A$", 2: "$B$"}   # power-box electrode keys
    s.net([('E', 1), ('P', 0, 1)])     # electrode 1 -> box0 pin1
    s.net([('P', 0, 3), ('P', 0, 4)])  # box0 pin3 -> pin4
    s.gnd_net(); s.vcc_net()           # wire pin7=GND, pin14=Vcc to power box
    return s

render_scene(wiring(), 'wiring_demo', 'build')   # -> build/wiring_demo.pdf
```

- Terminals: `('E', n)` = electrode key `n` (1..7); `('P', k, pin)` = pin
  `1..14` of logic box `k`. 74LS00 gate map: output pin `3←(1,2)`, `6←(4,5)`,
  `8←(9,10)`, `11←(12,13)`; `Vcc=14`, `GND=7`.
- **Point-to-point only — no branched cables.** Real jumper wires have two ends,
  so every drawn cable joins exactly two terminals; nothing branches (no
  T-junction / solder dot mid-wire). A net of k terminals is wired as a STAR
  fanning from its source terminal (the 極): `terminals[0]` of each `net([...])`
  is that source — an electrode key for an input, the driving gate-output pin
  for an internal signal. One independent cable runs from it to each other
  terminal; `gnd_net()`/`vcc_net()` fan the same way from the GND/Vcc terminal.
  (This is the **wiring diagram** rule; the Logisim `.circ` schematic side
  still uses `c.fan(...)` trunks/T-junctions, which is how Logisim nets join.)
- Convention used here: **outputs are read on the logic box's built-in pin LED,
  so they are NOT wired back to the power box** — only inputs come from
  electrode keys.
- Needs `lualatex` + a CJK font (box labels 論理箱/電源箱 are Japanese by
  default). For an all-Latin figure set `s.logic_label = "Logic box"` and
  `s.power_label = "Power box"`.
- See `examples/breadboard.py`.

## When something fails

Run `python3 -m logikit.doctor` (or `make doctor`) first — it reports which
capabilities are available (core / PNG / breadboard PDF) and prints how to
install whatever is missing. The tools also raise actionable errors rather than
bare tracebacks:

- `render.sh` checks for `java`/`javac` and the Logisim jar and tells you how to
  get each (`LOGISIM_JAR`, the download link).
- `render_scene` fails with an install hint if `lualatex` is missing, and a
  targeted CJK-font hint if compilation dies on a missing font. To avoid the CJK
  dependency entirely, use `DOC_LATIN` with ASCII `logic_label`/`power_label`:
  `render_scene(scene, name, doc=DOC_LATIN)`.
- `check(...)` / `truth_table(...)` raise a clear "generate it first with
  emit(...)" error if the `.circ`/`.spec` doesn't exist yet.

## Pitfalls

- **Don't skip the check.** A wrong circuit renders just as cleanly as a right
  one. Always `check(...)` and, for behaviour, `truth_table(...)`.
- **`nand_inv` marking:** mark its `pins`, not the tie node, or you get `[MISS]`.
- **Trunk overlaps:** give each `fan` a distinct `trunk_x` so vertical trunks of
  different nets don't overlap (overlap = short).
- **Render the `_fig` file**, not the `.circ` pin file, for clean figures.
- The Logisim jar is not bundled (large, third-party): set `LOGISIM_JAR`.
