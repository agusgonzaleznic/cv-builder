"""Render one merged CV file to a PDF and one preview image per page, with RenderCV."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

VENDOR = Path(__file__).parent / "vendor"
ICONS = ("fontawesome", "0.6.0")
ICON_IMPORT = f'#import "@preview/{ICONS[0]}:{ICONS[1]}"'


class RenderError(Exception):
    pass


def bundled_template() -> Path:
    import rendercv.renderer.pdf_png as pdf_png
    return Path(pdf_png.__file__).parent / "rendercv_typst"


def prepare_packages(folder: Path, *, ligatures: bool = False, kerning: bool = False) -> Path:
    """Build the Typst package folder a render uses: RenderCV's template with ligatures and
    kerning turned off, and the vendored icon package it imports. Fails loudly when RenderCV's
    template no longer has the shape this expects, instead of rendering something else.

    Ligatures off: with them on, Ghostscript lost every word with an ff, ffi or ffl glyph
    (traffic, efficient, office, offload), bold or plain. RenderCV's template sets them on
    directly under a comment that says it disables them.

    Kerning off: without ligatures, XCharter Bold kerns "f" and "l" 1.07 pt apart, just over the
    gap at which pdfminer's default settings insert a space, so bold "Airflow" read "Airf low".
    With kerning off the gap is gone and the page looks the same at print resolution.

    The two flags exist so the tests can render the failing cases as controls.
    """
    src = bundled_template()
    toml = (src / "typst.toml").read_text(encoding="utf-8")
    version = re.search(r'^version\s*=\s*"([^"]+)"', toml, re.M)
    lib = (src / "lib.typ").read_text(encoding="utf-8")
    if not version or ICON_IMPORT not in lib:
        raise RenderError("RenderCV's Typst template changed shape (version line or icon import "
                          "not found): this cv-builder release does not support it")
    if lib.count("    ligatures: true,\n") != 1 or "kerning:" in lib:
        raise RenderError("RenderCV's Typst template no longer sets ligatures where expected")
    lib = lib.replace("    ligatures: true,\n",
                      f"    ligatures: {str(ligatures).lower()},\n"
                      f"    kerning: {str(kerning).lower()},\n")

    if folder.exists():
        shutil.rmtree(folder)
    template = folder / "preview" / "rendercv" / version.group(1)
    template.mkdir(parents=True)
    (template / "typst.toml").write_text(toml, encoding="utf-8")
    (template / "lib.typ").write_text(lib, encoding="utf-8")
    shutil.copytree(VENDOR / f"{ICONS[0]}-{ICONS[1]}", folder / "preview" / ICONS[0] / ICONS[1])
    return folder


def render(merged_yaml: Path, out_dir: Path, send_name: str, scratch: Path, *,
           ligatures: bool = False, kerning: bool = False) -> Path:
    """Render `merged_yaml` into `out_dir/send_name` plus `preview_1.png`, `preview_2.png`, ...

    RenderCV resolves every output path against the folder of the file it reads, so each path is
    passed relative to it. Its Typst intermediate goes to `scratch`, keeping `out_dir` to what is
    sent and released. Old previews are removed first: a CV that shrank from two pages to one
    would otherwise keep a stale second preview.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    scratch.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("preview_*.png"):
        old.unlink()
    packages = prepare_packages(scratch / "typst-packages", ligatures=ligatures, kerning=kerning)
    base = merged_yaml.parent

    def rel(path: Path) -> str:
        return os.path.relpath(path, base)

    cmd = [sys.executable, "-m", "cv_builder._rendercv_shim", str(packages),
           "render", str(merged_yaml),
           "--output-folder", rel(scratch / "typst"),
           "--pdf-path", rel(out_dir / send_name),
           "--png-path", rel(out_dir / "preview.png"),
           "--dont-generate-markdown"]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    pdf = out_dir / send_name
    if proc.returncode != 0 or not pdf.exists():
        tail = "\n".join((proc.stdout + proc.stderr).strip().splitlines()[-25:])
        raise RenderError(tail or f"rendercv exited with {proc.returncode}")
    return pdf
