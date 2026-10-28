"""Run RenderCV's own command line against the Typst package folder cvcite prepared, with its
network access turned off.

Usage: python -P -m cvcite._rendercv_shim <package-folder> render <rendercv arguments>

RenderCV hands Typst a package folder holding only its own template, and that template imports an
icon package from the network on every render, into a cache in the home directory. cvcite's
folder holds the template (ligatures and kerning off) and the icon package (vendored). Replacing
`get_package_path` before the first compile is all it takes: the compiler looks it up when it is
created.

RenderCV's command line also checks PyPI for a newer release on every run, in a background thread,
with TLS verification turned off, and caches the answer in the home directory. cvcite pins the
version anyway, so the check is replaced with nothing. With both in place a render makes no
network request and writes nothing outside the build.
"""

from __future__ import annotations

import pathlib
import sys


def apply_patches(package_folder: pathlib.Path) -> None:
    """Point RenderCV at cvcite's package folder and switch off its update check. Fails closed:
    on a RenderCV without these functions, assigning them would do nothing and the render would
    quietly fetch the icon package, keep ligatures on and call PyPI."""
    from importlib.metadata import version

    from rendercv.cli import app
    from rendercv.renderer import pdf_png

    if version("rendercv") != "2.8":
        sys.exit(f"cvcite: RenderCV {version('rendercv')} is installed; this cvcite release "
                 "supports RenderCV 2.8 only")

    for module, name in ((pdf_png, "get_package_path"), (app, "warn_if_new_version_is_available")):
        if not callable(getattr(module, name, None)):
            sys.exit(f"cvcite: RenderCV changed shape (no {module.__name__}.{name}); this cvcite "
                     "release supports RenderCV 2.8 only")
    pdf_png.get_package_path = lambda: package_folder
    app.warn_if_new_version_is_available = lambda: None


def main() -> int:
    apply_patches(pathlib.Path(sys.argv.pop(1)).resolve())
    from rendercv.cli.entry_point import entry_point

    sys.argv[0] = "rendercv"
    return entry_point() or 0


if __name__ == "__main__":
    sys.exit(main())
