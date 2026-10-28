"""Run RenderCV's own command line against the Typst package folder cv-builder prepared.

Usage: python -m cv_builder._rendercv_shim <package-folder> render <rendercv arguments>

RenderCV hands Typst a package folder holding only its own template, and that template imports an
icon package from the network on every render, into a cache in the home directory. cv-builder's
folder holds the template (ligatures off) and the icon package (vendored), so a render needs no
network and writes nothing outside the build. Replacing `get_package_path` before the first
compile is all it takes: the compiler looks it up when it is created.
"""

from __future__ import annotations

import pathlib
import sys


def main() -> int:
    package_folder = pathlib.Path(sys.argv.pop(1)).resolve()
    from rendercv.cli.entry_point import entry_point
    from rendercv.renderer import pdf_png

    # Fail closed: on a RenderCV without this function, assigning it would do nothing and the
    # render would quietly fetch the icon package and keep ligatures on.
    if not callable(getattr(pdf_png, "get_package_path", None)):
        sys.exit("cv-builder: RenderCV changed shape (no pdf_png.get_package_path); this "
                 "cv-builder release supports RenderCV 2.8 only")
    pdf_png.get_package_path = lambda: package_folder
    sys.argv[0] = "rendercv"
    return entry_point() or 0


if __name__ == "__main__":
    sys.exit(main())
