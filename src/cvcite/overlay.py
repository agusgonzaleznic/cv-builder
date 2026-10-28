"""Build each variant from one master file, so versions of a CV can never drift apart.

Two hand-kept CVs end up contradicting each other: a figure updated in one and not the other, two
different stacks for the same job. So the master (`cv.yaml`) holds every fact, and each file in
`variants/` is a thin overlay that changes only positioning (headline, summary, bolded keywords,
the skills line) and names the bullets to drop so that variant fits its page budget.

Overlay format (`variants/<name>.yaml`):

    _meta:   name and description, for people
    _omit:   substrings; every bullet containing one is dropped
    cv: / design: / settings: / locale:   merged over the master (mappings merge, lists replace)

A variant's skills line may narrow or drop the master's skills, never add one: a skill that is
not on the master's line is a fact that skipped the fact ledger.
"""

from __future__ import annotations

import copy
import io
import re
from dataclasses import dataclass, field
from pathlib import Path

from ruamel.yaml import YAML


def yaml_rt() -> YAML:
    y = YAML()
    y.preserve_quotes = True
    y.width = 4096  # never fold a long bullet
    return y


def load_yaml(path: Path):
    return yaml_rt().load(path.read_text(encoding="utf-8"))


def deep_merge(base, overlay):
    """Merge overlay onto base. Mappings merge recursively; anything else replaces."""
    if isinstance(base, dict) and isinstance(overlay, dict):
        out = dict(base)
        for key, value in overlay.items():
            out[key] = deep_merge(base.get(key), value) if key in base else value
        return out
    return overlay


def drop_omitted(node, needles: list[str]) -> int:
    """Remove every bullet containing one of `needles`. Returns how many were removed."""
    removed = 0
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "highlights" and isinstance(value, list):
                keep = [h for h in value if not any(n in str(h) for n in needles)]
                removed += len(value) - len(keep)
                node[key] = keep
            else:
                removed += drop_omitted(value, needles)
    elif isinstance(node, list):
        for item in node:
            removed += drop_omitted(item, needles)
    return removed


def skills_section(cv: dict | None, name: str = "Skills"):
    """The skills section of a `cv` mapping, matched case-insensitively."""
    sections = (cv or {}).get("sections") or {}
    for key, value in sections.items():
        if str(key).lower() == name.lower():
            return value
    return None


def skill_items(entries) -> dict[str, list[str]]:
    """Map each skills label to its items, splitting on commas outside parentheses:
    "Python (FastAPI, Django), Go" gives two items, not three."""
    out: dict[str, list[str]] = {}
    for entry in entries or []:
        if not isinstance(entry, dict):
            continue
        items, depth, cur = [], 0, ""
        for ch in str(entry.get("details", "")):
            depth += (ch == "(") - (ch == ")")
            if ch == "," and depth == 0:
                items.append(cur.strip())
                cur = ""
            else:
                cur += ch
        if cur.strip():
            items.append(cur.strip())
        out[str(entry.get("label", ""))] = items
    return out


def skills_outside_master(master: dict, merged: dict, section: str = "Skills") -> list[str]:
    """Every variant skill that is not an item, or part of one, on the master's skills line."""
    master_skills = skill_items(skills_section(master.get("cv"), section))
    variant_skills = skill_items(skills_section(merged.get("cv"), section))
    problems = []
    for label, items in variant_skills.items():
        if label not in master_skills:
            problems.append(f"label '{label}' is not on the master's skills line")
            continue
        for item in items:
            # Whole words only: "PostgreSQL" narrows "PostgreSQL 16", "Go" does not narrow
            # "Google Cloud".
            pattern = rf"(?<!\w){re.escape(item)}(?!\w)"
            if not any(re.search(pattern, m) for m in master_skills[label]):
                problems.append(f"'{item}' under '{label}' is not on the master's skills line")
    return problems


def semicolon_after_bold(merged: dict) -> list[str]:
    """Bold keywords followed by a semicolon. Bolding renders as Typst `#strong[...]`, and in
    Typst markup a `;` right after a code call ends the expression: it is consumed, not printed."""
    keywords = (merged.get("settings") or {}).get("bold_keywords") or []
    text = str(merged.get("cv") or {})
    return [str(k) for k in keywords if re.search(re.escape(str(k)) + r"\s*;", text)]


@dataclass
class Variant:
    name: str
    description: str
    data: dict
    removed: int
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def dump(self, path: Path, master_name: str, overlay_name: str) -> None:
        """Write the merged CV for RenderCV. Plain data only: the master's and the overlay's YAML
        comments may hold private notes, and this file ships in every release zip. The header
        names only the files: a free-text description could carry a line break and inject YAML
        that was never checked."""
        header = (f"# GENERATED by cvcite from {master_name} + {overlay_name}\n"
                  "# Do not edit: change the master or the overlay instead.\n")
        buf = io.StringIO()
        yaml_rt().dump(plain(self.data), buf)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(header + buf.getvalue(), encoding="utf-8")


def plain(node):
    """The same data as built-in dicts, lists and scalars, without ruamel's comments."""
    if isinstance(node, dict):
        return {str(k): plain(v) for k, v in node.items()}
    if isinstance(node, list):
        return [plain(v) for v in node]
    if isinstance(node, str):
        return str(node)
    return node


def build_variant(master_path: Path, overlay_path: Path, skills: str = "Skills") -> Variant:
    master = load_yaml(master_path)
    overlay = load_yaml(overlay_path) or {}
    meta = overlay.pop("_meta", None) or {}
    omit = [str(n) for n in (overlay.pop("_omit", None) or [])]
    name = str(meta.get("name", overlay_path.stem))

    merged = deep_merge(copy.deepcopy(master), overlay)
    removed = drop_omitted(merged, omit) if omit else 0
    variant = Variant(name=name, description=str(meta.get("description", "")), data=merged,
                      removed=removed)

    if name != overlay_path.stem:
        variant.errors.append(f"_meta.name '{name}' differs from the file name "
                              f"'{overlay_path.stem}'; the output folder is named after the file")
    # A pattern that matches nothing is almost always a typo or a reworded bullet.
    master_text = str(master)
    unmatched = [n for n in omit if n not in master_text]
    if unmatched:
        variant.warnings.append(f"omit pattern(s) matched nothing in the master: {unmatched}")
    for keyword in semicolon_after_bold(merged):
        variant.warnings.append(f"bold keyword '{keyword}' is followed by ';', which Typst drops "
                                "from the PDF; reword with '.' or ', and'")
    variant.errors += [f"skills line: {p}" for p in skills_outside_master(master, merged, skills)]
    return variant
