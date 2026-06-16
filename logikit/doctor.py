#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Environment check: report which logikit capabilities work here, and how to
fix the ones that don't.

    python3 -m logikit.doctor

Exit code 0 if every capability is available, 1 if something optional is
missing (the core — generate / check / simulate — needs nothing but Python and
is always reported OK).
"""
from __future__ import annotations

import platform
import sys

from . import _env

OK = "✓"      # ✓
NO = "✗"      # ✗
UNK = "?"


def _line(mark, name, detail=""):
    print(f"  {mark}  {name}" + (f"  —  {detail}" if detail else ""))


def main(argv=None):
    print("logikit environment check\n")

    # --- core (always available) ---
    print("core: generate / check / simulate  (pure standard library)")
    _line(OK, f"Python {platform.python_version()}",
          "OK" if sys.version_info >= (3, 9) else "WARNING: 3.9+ recommended")
    print()

    all_ok = sys.version_info >= (3, 9)

    # --- PNG rendering ---
    print("render to PNG:  needs a JDK + the Logisim jar")
    java = _env.find_executable('java')
    javac = _env.find_executable('javac')
    jar = _env.find_logisim_jar()
    _line(OK if java else NO, "java", java or _env.hint_java())
    _line(OK if javac else NO, "javac", javac or _env.hint_java())
    _line(OK if jar else NO, "Logisim jar", jar or _env.hint_logisim())
    png_ok = bool(java and javac and jar)
    print(f"  => PNG rendering: {'available' if png_ok else 'NOT available'}\n")
    all_ok = all_ok and png_ok

    # --- breadboard PDF ---
    print("breadboard PDF (結線図):  needs lualatex (+ a CJK font for JP labels)")
    lualatex = _env.find_executable('lualatex')
    _line(OK if lualatex else NO, "lualatex", lualatex or _env.hint_lualatex())
    font = _env.has_cjk_font()
    if font is True:
        _line(OK, "CJK font (Harano Aji)", "found")
    elif font is False:
        _line(NO, "CJK font (Harano Aji)", _env.hint_cjk_font())
    else:
        _line(UNK, "CJK font", "could not detect (no `fc-list`); assuming present")
    pdf_ok = bool(lualatex) and font is not False
    print(f"  => breadboard PDF: {'available' if pdf_ok else 'NOT available'}\n")
    all_ok = all_ok and pdf_ok

    if all_ok:
        print("All capabilities available.")
    else:
        print("Some optional capabilities are unavailable (see hints above). "
              "Core generation/check/simulation still works.")
    return 0 if all_ok else 1


if __name__ == '__main__':
    sys.exit(main())
