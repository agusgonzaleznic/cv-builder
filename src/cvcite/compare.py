"""`cvcite compare`: the roles of the CV against a LinkedIn data export. Titles, employers and
dates are facts, so where the two disagree one of them is wrong, and a recruiter who reads both
will notice. Wording is left to the cv-presence-audit skill; this checks only what must match."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .checks import parse_date
from .ingest import linkedin_date


def norm(text: str) -> str:
    text = re.sub(r"[^\w\s&]", " ", str(text or "").lower())
    text = re.sub(r"\b(gmbh|ltd|limited|inc|llc|s\.?a|sa|se|ag|plc|bv)\b", " ", text)
    return re.sub(r"\s+", " ", text).strip()


@dataclass
class Row:
    status: str  # "match", "differs", "only on the CV", "only on LinkedIn"
    company: str
    detail: str


def _month(value) -> tuple | str | None:
    parsed = parse_date(value) if value not in (None, "") else None
    return parsed


def same_date(cv_value, li_value) -> bool:
    a, b = _month(cv_value), _month(li_value if li_value is not None else "present")
    if a is None or b is None or a == "present" or b == "present":
        return a == b
    if not a[1] or not b[1]:  # a year-only date matches any month of that year
        return a[0] == b[0]
    return a == b


def compare_roles(cv: dict, export: dict) -> list[Row]:
    experience = []
    for name, items in ((cv or {}).get("sections") or {}).items():
        if str(name).lower() in ("experience", "work", "employment"):
            experience += [e for e in items or [] if isinstance(e, dict)]
    positions = [dict(p) for p in export.get("positions") or []]
    used: set[int] = set()
    rows: list[Row] = []
    for entry in experience:
        company, title = entry.get("company", ""), entry.get("position", "")
        candidates = [i for i, p in enumerate(positions)
                      if i not in used and norm(p.get("Company Name")) == norm(company)]
        if not candidates:
            rows.append(Row("only on the CV", company, f"{title}: no LinkedIn position at "
                                                        "this company"))
            continue
        # Prefer the position with the same title, then the one with the same start.
        best = min(candidates, key=lambda i: (
            norm(positions[i].get("Title")) != norm(title),
            not same_date(entry.get("start_date"), linkedin_date(positions[i].get("Started On")))))
        used.add(best)
        p = positions[best]
        start, end = linkedin_date(p.get("Started On")), linkedin_date(p.get("Finished On"))
        problems = []
        if norm(p.get("Title")) != norm(title):
            problems.append(f"title: CV '{title}', LinkedIn '{p.get('Title')}'")
        if not same_date(entry.get("start_date"), start):
            problems.append(f"start: CV {entry.get('start_date')}, LinkedIn {start}")
        if not same_date(entry.get("end_date", "present"), end):
            problems.append(f"end: CV {entry.get('end_date', 'present')}, LinkedIn "
                            f"{end or 'present'}")
        rows.append(Row("differs" if problems else "match", company,
                        "; ".join(problems) or title))
    for i, p in enumerate(positions):
        if i not in used:
            rows.append(Row("only on LinkedIn", p.get("Company Name", ""),
                            f"{p.get('Title', '')}, {p.get('Started On', '')} to "
                            f"{p.get('Finished On') or 'present'}"))
    return rows
