"""logikit — generate, render and verify Logisim figures from Python.

A small, dependency-free toolkit for producing publication-quality digital-logic
figures (gate schematics, breadboard/DIP wiring diagrams) and proving they are
correct, without drawing anything by hand.

Submodules:

* :mod:`logikit.circ`    — a tiny DSL that emits real-wire Logisim ``.circ``
                           files (plus a label-only figure variant and a wiring
                           spec).
* :mod:`logikit.check`   — static connectivity check of a ``.circ`` against its
                           spec (catches shorts and opens).
* :mod:`logikit.sim`     — extract a gate netlist and relax it to a fixpoint
                           (truth tables; oscillation detection).
* :mod:`logikit.wiring`  — breadboard / DIP wiring diagrams (結線図) as vector
                           PDF via TikZ + LuaLaTeX.

A companion Java renderer (``render/LogiRender.java``) turns a ``.circ`` into a
PNG using Logisim's own drawing code.
"""
import importlib

__version__ = "0.1.0"
__all__ = [
    "Circ", "emit",
    "check",
    "netlist_from_circ", "simulate", "truth_table", "truth_table_str",
    "format_table",
    "Scene", "render_scene",
]

# Map each public name to the submodule that defines it.  We resolve lazily via
# PEP 562 __getattr__ instead of importing eagerly, so running a submodule as a
# script (`python -m logikit.check`) doesn't trip runpy's "found in sys.modules
# before execution" warning.
_LAZY = {
    "Circ": "circ", "emit": "circ",
    "check": "check",
    "netlist_from_circ": "sim", "simulate": "sim", "truth_table": "sim",
    "truth_table_str": "sim", "format_table": "sim",
    "Scene": "wiring", "render_scene": "wiring",
}


def __getattr__(name):
    if name in _LAZY:
        mod = importlib.import_module(f".{_LAZY[name]}", __name__)
        return getattr(mod, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    return sorted(__all__)
