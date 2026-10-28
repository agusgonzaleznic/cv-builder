"""Settings for one CV repository, read from `cvcite.toml` at its root. Every key is optional;
a missing file means the defaults."""

from __future__ import annotations

import math
import re
import tomllib
from dataclasses import dataclass, field, fields
from pathlib import Path

from .gate import DEFAULT_BANNED, MIN_TEXT_CONTRAST

CONFIG_NAME = "cvcite.toml"


def parse_codepoints(values: list[str]) -> tuple[str, ...]:
    """Read characters written as "U+2014" (or as the character itself) into a tuple. Code
    points keep the config file free of the characters it bans."""
    out = []
    for value in values:
        m = re.fullmatch(r"[Uu]\+([0-9A-Fa-f]{4,6})", str(value).strip())
        out.append(chr(int(m.group(1), 16)) if m else str(value))
    return tuple(out)


@dataclass
class Config:
    root: Path
    master: str = "cv.yaml"
    variants: str = "variants"
    facts: str = "facts.yaml"
    build_dir: str = "build"
    send_name: str = "CV.pdf"
    pages: int = 2
    skills_section: str = "Skills"
    extractors: list[str] = field(default_factory=list)
    banned: tuple[str, ...] = DEFAULT_BANNED
    min_contrast: float = MIN_TEXT_CONTRAST
    market: str = "international"

    @property
    def master_path(self) -> Path:
        return self.root / self.master

    @property
    def variants_path(self) -> Path:
        return self.root / self.variants

    @property
    def facts_path(self) -> Path:
        return self.root / self.facts

    @property
    def build_path(self) -> Path:
        return self.root / self.build_dir

    def overlays(self) -> list[Path]:
        return sorted(self.variants_path.glob("*.yaml")) if self.variants_path.is_dir() else []


SECTIONS = {
    "build": {"master", "variants", "facts", "build_dir", "send_name", "pages", "skills_section"},
    "gate": {"extractors", "banned_characters", "min_contrast"},
    "privacy": {"market"},
}
MARKETS = {"international", "us"}


def load(root: Path) -> Config:
    """Load `cvcite.toml` from `root`. Unknown sections or keys are an error: a typo in a
    setting would otherwise silently fall back to its default."""
    cfg = Config(root=root.resolve())
    path = root / CONFIG_NAME
    if not path.exists():
        return cfg
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    for section, values in data.items():
        if section not in SECTIONS:
            raise ValueError(f"{CONFIG_NAME}: unknown section [{section}]")
        for key in values:
            if key not in SECTIONS[section]:
                raise ValueError(f"{CONFIG_NAME}: unknown key '{key}' in [{section}]")
    build = data.get("build", {})
    known = {f.name for f in fields(Config)}
    for key, value in build.items():
        if key in known:
            setattr(cfg, key, value)
    gate = data.get("gate", {})
    if "extractors" in gate:
        cfg.extractors = [str(e) for e in gate["extractors"]]
    if "banned_characters" in gate:
        cfg.banned = parse_codepoints(gate["banned_characters"])
    if "min_contrast" in gate:
        cfg.min_contrast = float(gate["min_contrast"])
    market = data.get("privacy", {}).get("market", cfg.market)
    if market not in MARKETS:
        raise ValueError(f"{CONFIG_NAME}: market '{market}' is not one of {sorted(MARKETS)}")
    cfg.market = market
    if not isinstance(cfg.pages, int) or isinstance(cfg.pages, bool) or cfg.pages < 1:
        raise ValueError(f"{CONFIG_NAME}: pages must be a whole number of at least 1")
    name = cfg.send_name
    if (not isinstance(name, str) or "/" in name or "\\" in name or name.startswith(("-", "."))
            or not name.lower().endswith(".pdf")):
        raise ValueError(f"{CONFIG_NAME}: send_name must be a plain file name ending in .pdf")
    for key in ("master", "variants", "facts", "build_dir"):
        value = getattr(cfg, key)
        rel = Path(str(value))
        if not isinstance(value, str) or not value or rel.is_absolute() or ".." in rel.parts:
            raise ValueError(f"{CONFIG_NAME}: {key} must be a path inside the repository")
    if not (isinstance(cfg.min_contrast, float) and math.isfinite(cfg.min_contrast)
            and 1.0 <= cfg.min_contrast <= 21.0):
        raise ValueError(f"{CONFIG_NAME}: min_contrast must be a number from 1 to 21")
    return cfg
