"""Package the build folder for a release: `build.zip`, `SHA256SUMS` and `MANIFEST.md`.

The build folder must hold exactly what `cvcite build` makes for each overlay: the PDF under
its send name, one preview image per page and the merged YAML. A missing or extra file fails, so a
release never ships a stale or stray file. `shasum -a 256 -c SHA256SUMS`, run in the folder that
holds `build/`, verifies every file.
"""

from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path

from .config import Config

# One fixed timestamp for every entry, so the same build folder always zips to the same bytes.
ZIP_DATE = (1980, 1, 1, 0, 0, 0)


def expected_files(cfg: Config) -> set[str]:
    out: set[str] = set()
    for overlay in cfg.overlays():
        v = overlay.stem
        out |= {f"{v}/{cfg.send_name}", f"cv-{v}.yaml"}
        out |= {f"{v}/preview_{n}.png" for n in range(1, cfg.pages + 1)}
    return out


def package(cfg: Config, out_dir: Path | None = None) -> tuple[bool, list[str]]:
    """Zip the build folder into `out_dir` (default `.tmp/release`). Returns (ok, messages)."""
    build = cfg.build_path
    out = out_dir or cfg.root / ".tmp" / "release"
    if not build.is_dir():
        return False, [f"no {cfg.build_dir}/ folder: run `cvcite build` first"]
    present = {p.relative_to(build).as_posix() for p in build.rglob("*")
               if p.is_file() and p.name != ".DS_Store"}
    expected = expected_files(cfg)
    if not expected:
        return False, [f"no overlays in {cfg.variants}/: nothing to package"]
    missing, extra = sorted(expected - present), sorted(present - expected)
    messages = [f"missing {cfg.build_dir}/{rel}: run `cvcite build`" for rel in missing]
    messages += [f"unexpected {cfg.build_dir}/{rel}: delete {cfg.build_dir}/ and build again"
                 for rel in extra]
    if missing or extra:
        return False, messages

    out.mkdir(parents=True, exist_ok=True)
    sums, rows = [], []
    with zipfile.ZipFile(out / "build.zip", "w") as zf:
        for rel in sorted(expected):
            data = (build / rel).read_bytes()
            info = zipfile.ZipInfo(f"build/{rel}", date_time=ZIP_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16  # a regular file, rw-r--r--
            zf.writestr(info, data)
            sums.append(f"{hashlib.sha256(data).hexdigest()}  build/{rel}")
            rows.append(f"| `build/{rel}` | {len(data):,} bytes |")
    (out / "SHA256SUMS").write_text("\n".join(sums) + "\n", encoding="utf-8")
    (out / "MANIFEST.md").write_text("| File | Size |\n|---|---|\n" + "\n".join(rows) + "\n",
                                     encoding="utf-8")
    size = (out / "build.zip").stat().st_size
    return True, [f"packaged {len(expected)} files into {out / 'build.zip'} ({size:,} bytes), "
                  "plus SHA256SUMS and MANIFEST.md"]
