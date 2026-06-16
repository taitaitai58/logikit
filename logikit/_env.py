#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Locate the optional external tools logikit can use, and turn a missing one
into an actionable message instead of a raw traceback.

The core (generate / check / simulate) is pure standard library and always
works. Rendering to PNG needs a JDK + the Logisim jar; the breadboard PDF needs
``lualatex`` (+ a CJK font for the default Japanese labels). These helpers let
every entry point fail with "here's what's missing and how to install it".
"""
from __future__ import annotations

import glob
import os
import shutil

LOGISIM_DOWNLOAD = "https://github.com/logisim-evolution/logisim-evolution/releases"


def find_executable(name):
    """Absolute path of ``name`` on PATH, or ``None``."""
    return shutil.which(name)


def find_logisim_jar():
    """Locate the Logisim-evolution ``…-all.jar``.

    Order: ``$LOGISIM_JAR``, the macOS app bundle, then ``~/Downloads``.
    Returns the path or ``None``.
    """
    env = os.environ.get('LOGISIM_JAR')
    if env and os.path.isfile(env):
        return env
    patterns = [
        '/Applications/Logisim-evolution.app/Contents/app/logisim-evolution-*-all.jar',
        os.path.expanduser('~/Downloads/logisim-evolution-*-all.jar'),
    ]
    for pat in patterns:
        for c in sorted(glob.glob(pat)):
            if os.path.isfile(c):
                return c
    return None


def has_cjk_font(family='HaranoAjiMincho'):
    """Best-effort check for a CJK font usable by LuaLaTeX.

    Prefers ``kpsewhich`` (TeX's own font tree — the same one LuaLaTeX/luaotfload
    read, so it matches what a render would actually find) and falls back to
    ``fc-list``.  Returns ``True``/``False``, or ``None`` when no probe tool is
    available.  A ``True`` from either probe is trusted (avoids false negatives:
    fontconfig often can't see a font that lives only in TeX's tree).
    """
    import subprocess

    kp = shutil.which('kpsewhich')
    if kp:
        try:
            r = subprocess.run([kp, f'{family}-Regular.otf'],
                               capture_output=True, text=True, timeout=20)
            if r.returncode == 0 and r.stdout.strip():
                return True
        except Exception:
            pass

    fc = shutil.which('fc-list')
    if fc:
        try:
            out = subprocess.run([fc, ':', 'family'], capture_output=True,
                                 text=True, timeout=20).stdout
            if family.lower() in out.lower():
                return True
        except Exception:
            pass

    # Tools exist but neither found it -> genuinely absent; else unknown.
    return False if (kp or fc) else None


# ---- hint strings -------------------------------------------------------
def hint_java():
    return ("Install a JDK (provides `java`/`javac`):\n"
            "  macOS:  brew install temurin        (or any OpenJDK ≥ 11)\n"
            "  Linux:  sudo apt install default-jdk")


def hint_logisim():
    return (f"Set LOGISIM_JAR to the Logisim-evolution '…-all.jar':\n"
            f"  export LOGISIM_JAR=/path/to/logisim-evolution-X.Y.Z-all.jar\n"
            f"  download: {LOGISIM_DOWNLOAD}\n"
            f"  (on macOS, installing Logisim-evolution.app is auto-detected)")


def hint_lualatex():
    return ("Install LuaLaTeX (part of a TeX distribution):\n"
            "  macOS:  brew install --cask mactex-no-gui   (or install MacTeX)\n"
            "  Linux:  sudo apt install texlive-luatex texlive-lang-japanese\n"
            "          (or a full `texlive-full`)")


def hint_cjk_font():
    return ("The default breadboard labels are Japanese and need a CJK font\n"
            "(e.g. Harano Aji, shipped with TeX Live's texlive-lang-japanese).\n"
            "Or render an all-Latin figure with no CJK font:\n"
            "  from logikit.wiring import DOC_LATIN\n"
            "  scene.logic_label, scene.power_label = 'Logic box', 'Power box'\n"
            "  render_scene(scene, name, doc=DOC_LATIN)")
