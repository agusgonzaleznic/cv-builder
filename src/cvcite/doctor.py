"""`cvcite doctor`: is everything a build needs in place?"""

from __future__ import annotations

import platform
import subprocess
import tempfile
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from . import __version__, config, gate, render

RENDERCV = "2.8"


def _version(dist: str) -> str:
    try:
        return version(dist)
    except PackageNotFoundError:
        return "missing"


def doctor(root: Path) -> int:
    problems = 0
    print(f"cvcite  {__version__}")
    print(f"python      {platform.python_version()}")
    rcv = _version("rendercv")
    print(f"rendercv    {rcv}" + ("" if rcv == RENDERCV else f"   PROBLEM: needs {RENDERCV}"))
    problems += rcv != RENDERCV
    try:
        with tempfile.TemporaryDirectory() as tmp:
            render.prepare_packages(Path(tmp) / "packages")
        print("template    RenderCV's Typst template has the expected shape")
    except Exception as exc:  # report, do not crash: this is the diagnostic
        print(f"template    PROBLEM: {exc}")
        problems += 1
    names = gate.available_extractors()
    print(f"extractors  {', '.join(names) or 'none'}"
          + ("" if len(names) >= 2 else "   PROBLEM: the gate needs two"))
    problems += len(names) < 2
    if "ghostscript" in names:
        gs = subprocess.run(["gs", "--version"], capture_output=True, text=True).stdout.strip()
        print(f"ghostscript {gs}")
    else:
        print("ghostscript not installed (optional: a third extractor for the gate)")
    try:
        cfg = config.load(root)
        print(f"config      {config.CONFIG_NAME} {'read' if (root / config.CONFIG_NAME).exists() else 'absent, defaults'}; "
              f"{len(cfg.overlays())} variant(s)")
    except ValueError as exc:
        print(f"config      PROBLEM: {exc}")
        problems += 1
    print("DOCTOR: all good" if not problems else f"DOCTOR: {problems} problem(s)")
    return 1 if problems else 0
