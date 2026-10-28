"""Checks that need no render: dates, the RenderCV traps, banned characters, skills backed by
bullets, every number traced to the fact ledger, and privacy. Each returns `Issue`s; an error
fails `cv-builder check` and `cv-builder build`, a warning is shown and passes."""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass

from .overlay import skill_items, skills_section


@dataclass(frozen=True)
class Issue:
    level: str  # "error" or "warning"
    where: str
    message: str

    def __str__(self) -> str:
        return f"{self.level.upper():<7} {self.where}: {self.message}"


def entries(cv: dict):
    """Yield (where, section name, entry) for every entry that is a mapping."""
    for name, items in ((cv or {}).get("sections") or {}).items():
        for i, entry in enumerate(items or []):
            if isinstance(entry, dict):
                yield f"cv.sections.{name}[{i}]", str(name), entry


def strings(cv: dict):
    """Yield (where, text) for every string in the `cv` mapping."""
    def walk(node, where):
        if isinstance(node, dict):
            for key, value in node.items():
                yield from walk(value, f"{where}.{key}")
        elif isinstance(node, list):
            for i, item in enumerate(node):
                yield from walk(item, f"{where}[{i}]")
        elif isinstance(node, str):
            yield where, node
    yield from walk(cv or {}, "cv")


def prose(cv: dict):
    """Yield (where, text) for every bullet, entry summary and plain text entry (a summary
    paragraph, a certification line): the claims a reader reads."""
    for name, items in ((cv or {}).get("sections") or {}).items():
        for i, entry in enumerate(items or []):
            where = f"cv.sections.{name}[{i}]"
            if isinstance(entry, str):
                yield where, entry
            elif isinstance(entry, dict):
                for j, bullet in enumerate(entry.get("highlights") or []):
                    yield f"{where}.highlights[{j}]", str(bullet)
                if isinstance(entry.get("summary"), str):
                    yield f"{where}.summary", entry["summary"]


# ------------------------------------------------------------------------------------------ dates

DATE_RE = re.compile(r"^(\d{4})(?:-(\d{2}))?(?:-(\d{2}))?$")


def parse_date(value) -> tuple[int, int] | None | str:
    """(year, month) for a RenderCV date, "present" for the present, None when unparseable.
    A bare year counts as its January for ordering, and its December as an end date."""
    if isinstance(value, int):
        return (value, 0)
    if isinstance(value, dt.date):
        return (value.year, value.month)
    text = str(value).strip().lower()
    if text == "present":
        return "present"
    m = DATE_RE.match(text)
    if not m:
        return None
    return (int(m.group(1)), int(m.group(2)) if m.group(2) else 0)


def check_dates(cv: dict, today: dt.date | None = None) -> list[Issue]:
    today = today or dt.date.today()
    now = (today.year, today.month)
    issues: list[Issue] = []
    spans: dict[str, list[tuple[str, tuple, tuple, str]]] = {}
    for where, section, entry in entries(cv):
        start, end = entry.get("start_date"), entry.get("end_date")
        if start is None and end is None:
            continue
        for key, raw in (("start_date", start), ("end_date", end)):
            if raw is None:
                continue
            if isinstance(raw, str) and re.fullmatch(r"\d{4}", raw.strip()):
                issues.append(Issue("warning", f"{where}.{key}",
                                    f"the year {raw} is quoted; RenderCV may print it as "
                                    "January of that year. Write it unquoted"))
            parsed = parse_date(raw)
            if parsed is None:
                issues.append(Issue("error", f"{where}.{key}",
                                    f"'{raw}' is not YYYY, YYYY-MM, YYYY-MM-DD or present"))
            elif parsed != "present" and parsed > now:
                issues.append(Issue("error", f"{where}.{key}", f"{raw} is in the future"))
        s, e = parse_date(start) if start is not None else None, parse_date(end)
        if isinstance(s, tuple):
            e_cmp = now if e in (None, "present") else e
            if isinstance(e_cmp, tuple):
                if (s[0], s[1] or 1) > (e_cmp[0], e_cmp[1] or 12):
                    issues.append(Issue("error", where, f"starts ({start}) after it ends ({end})"))
                company = str(entry.get("company") or entry.get("institution") or "")
                spans.setdefault(section, []).append((where, s, e_cmp, company))
    for section, items in spans.items():
        starts = [(s[0], s[1] or 1) for _, s, _, _ in items]
        if starts != sorted(starts, reverse=True):
            issues.append(Issue("warning", f"cv.sections.{section}",
                                "entries are not newest first"))
        ordered = sorted(items, key=lambda t: (t[1][0], t[1][1] or 1))
        for (w1, _, e1, c1), (w2, s2, _, c2) in zip(ordered, ordered[1:]):
            # A year-only date says nothing about the month: "2018" then "2018-06" may touch,
            # overlap or leave a gap. Compare months only when both sides name one.
            if not e1[1] or not s2[1]:
                months = 12 * (s2[0] - e1[0]) if s2[0] != e1[0] else 0
            else:
                months = (s2[0] - e1[0]) * 12 + (s2[1] - e1[1])
            if months < 0 and c1 != c2:
                issues.append(Issue("warning", w2, f"overlaps {w1} by {-months} month(s); "
                                    "fine for concurrent roles, but say so in the text"))
            elif months > 6 and section.lower() in ("experience", "work", "employment"):
                issues.append(Issue("warning", w2, f"{months} months after {w1} ended: "
                                    "a reader will ask about the gap"))
    return issues


# --------------------------------------------------------------------------------- text traps

def check_text(cv: dict, settings: dict | None, banned: tuple[str, ...]) -> list[Issue]:
    issues: list[Issue] = []
    for where, text in strings(cv):
        if "TODO" in text:
            issues.append(Issue("error", where, "still holds a TODO: fill it in from the fact "
                                "ledger, or take it out"))
        for ch in banned:
            if ch in text:
                issues.append(Issue("error", where, f"contains the banned character "
                                    f"U+{ord(ch):04X}: use a colon, a comma or parentheses"))
    for where, text in prose(cv):
        if " - " in text and where.split(".")[-1].startswith("highlights"):
            issues.append(Issue("error", where, "' - ' inside a bullet: RenderCV splits it into "
                                "two bullets. Use a colon or a comma"))
    keywords = [str(k) for k in ((settings or {}).get("bold_keywords") or [])]
    for where, _, entry in entries(cv):
        for key in ("position", "company", "institution", "degree", "area", "title", "name"):
            value = entry.get(key)
            if isinstance(value, str):
                for kw in keywords:
                    if kw and kw in value:
                        issues.append(Issue("warning", f"{where}.{key}",
                                            f"the bold keyword '{kw}' is in this field, where "
                                            "its asterisks can show up literally"))
    return issues


# ------------------------------------------------------------------------- skills and the ledger

def skill_parts(item: str) -> list[str]:
    """The names an item stands for: "Spark/PySpark (MLlib)" stands for Spark, PySpark, MLlib."""
    return [p.strip() for p in re.split(r"[/()]", item) if p.strip()]


def check_skills_backed(cv: dict, section: str = "Skills") -> list[Issue]:
    """Every skill on the skills line should appear in a bullet or summary of the same CV."""
    text = " ".join(t for _, t in prose(cv)).lower()
    issues = []
    for label, items in skill_items(skills_section(cv, section)).items():
        for item in items:
            if not any(re.search(rf"(?<!\w){re.escape(p.lower())}(?!\w)", text)
                       for p in skill_parts(item)):
                issues.append(Issue("warning", f"cv.sections.{section} ({label})",
                                    f"'{item}' appears in no bullet or summary: back it with "
                                    "one, or drop it from this skills line"))
    return issues


NUMBER_RE = re.compile(r"(?<![\w.])(?:[$€£]\s?)?\d[\d,.]*(?:\s?(?:%|k|K|M|B|x))?(?![\w])")


def numbers(text: str) -> set[str]:
    """Numeric claims in a text, normalised: "40 %" and "40%" are the same claim."""
    return {re.sub(r"\s+", "", m).rstrip(".,") for m in NUMBER_RE.findall(text)}


def check_numbers_in_ledger(cv: dict, facts: list[dict] | None) -> list[Issue]:
    """Every number in a bullet or summary must appear in a fact of the ledger. A figure no fact
    holds was estimated, inferred or remembered, which is how CVs end up overclaiming. A number
    that only a `visibility: private` fact holds must not reach the CV at all."""
    if facts is None:
        return [Issue("warning", "facts.yaml", "no fact ledger: numbers in bullets go unchecked")]
    shareable: set[str] = set()
    private: set[str] = set()
    for fact in facts:
        found = numbers(str(fact.get("text", "")))
        if str(fact.get("visibility", "public")) == "private":
            private |= found
        else:
            shareable |= found
    issues = []
    for where, text in prose(cv):
        for number in sorted(numbers(text) - shareable):
            if re.fullmatch(r"(19|20)\d\d", number):
                continue  # a year is checked by the date checks
            if number in private:
                issues.append(Issue("error", where, f"'{number}' comes from a private fact of "
                                    "the ledger and must not be on the CV"))
            else:
                issues.append(Issue("error", where, f"'{number}' is in no fact of the ledger: "
                                    "add the fact with its source first, or take the number out"))
    return issues


# ------------------------------------------------------------------------------------- privacy

PRIVATE_FIELDS = {
    "photo": "a photo",
    "date_of_birth": "a date of birth",
    "birth_date": "a date of birth",
    "birthday": "a date of birth",
    "nationality": "a nationality",
    "marital_status": "a marital status",
}
# Personal details a CV in these markets leaves out, as labels in the languages CVs are most often
# written in. A label with its value ("Date of birth: ...") is an error. The same words in running
# text ("built the passport scanning service") only warn: they may describe the work.
PRIVATE_LABELS = {
    "a date of birth": [
        "date of birth", "birth date", "birthdate", "born on", "geburtsdatum",
        "fecha de nacimiento", "date de naissance", "data di nascita", "data de nascimento",
        "geboortedatum", "data urodzenia"],
    "a marital status": [
        "marital status", "familienstand", "estado civil", "situation familiale", "état civil",
        "stato civile", "burgerlijke staat", "stan cywilny"],
    "a nationality": [
        "nationality", "citizenship", "staatsangehörigkeit", "nacionalidad", "nationalité",
        "nazionalità", "nacionalidade", "nationaliteit", "obywatelstwo"],
    "an identity, tax or bank number": [
        "passport number", "id card number", "identity card", "social security number",
        "national insurance number", "tax id", "steuer-id", "codice fiscale", "sort code"],
}
# Short identity and bank codes count only next to a value ("NIE: X1234567L", "CPF 123.456"),
# since as bare words several are ordinary words in some language.
ID_CODES = ["ssn", "nino", "dni", "nie", "nif", "cpf", "cbu", "bsn", "nir", "pesel",
            "curp", "rut", "iban", "svnr"]
PRIVATE_PATTERNS = [
    (r"wa\.me/", "a WhatsApp link", 0),
    (r"\b[A-Z]{2}\d{2}(?: ?[A-Z0-9]{4}){3,7}\b", "what looks like an IBAN", 0),
    (r"\b\d{3}-\d{2}-\d{4}\b", "what looks like a US Social Security number", 0),
    (r"\b(" + "|".join(ID_CODES) + r")\b\s*:?\s*[A-Z]?[\d][\d.\- /]{4,}", "an identity, tax or "
     "bank number", re.I),
]
STREET_RE = re.compile(
    r"\d+\s*\w*\s*(street|st\.|avenue|ave\.|road|rd\.|lane|stra(ss|ß)e|weg|platz|calle|avenida|"
    r"rue|via|viale|rua|straat|laan|ulica)\b|\b(street|stra(ss|ß)e|weg|platz|calle|avenida|rue|"
    r"via|rua|straat|laan|ulica)\s+\d+", re.I)


def check_privacy(cv: dict, market: str = "international") -> list[Issue]:
    """What a CV in the international and US markets leaves out: photo, date of birth,
    nationality, marital status, a street address, identity and bank numbers."""
    issues = []
    for key, what in PRIVATE_FIELDS.items():
        if (cv or {}).get(key):
            issues.append(Issue("error", f"cv.{key}", f"{what}: leave it out; it invites bias "
                                f"and no {market} employer needs it to shortlist you"))
    for where, text in strings(cv):
        for what, labels in PRIVATE_LABELS.items():
            for label in labels:
                if re.search(rf"\b{re.escape(label)}\s*:", text, re.I):
                    issues.append(Issue("error", where, f"{what}: leave it out of the CV"))
                elif re.search(rf"\b{re.escape(label)}\b", text, re.I):
                    issues.append(Issue("warning", where, f"mentions '{label}': fine if it "
                                        "describes the work, never your own "
                                        + what.split(" ", 1)[1]))
        for pattern, what, flags in PRIVATE_PATTERNS:
            if re.search(pattern, text, flags):
                issues.append(Issue("error", where, f"{what}: leave it out of the CV"))
    location = str((cv or {}).get("location") or "")
    if STREET_RE.search(location) or re.search(r"\d{4,}", location):
        issues.append(Issue("error", "cv.location",
                            "looks like a street address or postcode: give the city and "
                            "country only"))
    return issues


def run_all(merged: dict, *, banned: tuple[str, ...], facts: list[dict] | None,
            market: str, skills: str = "Skills",
            today: dt.date | None = None) -> list[Issue]:
    cv = merged.get("cv") or {}
    return (check_dates(cv, today) + check_text(cv, merged.get("settings"), banned)
            + check_skills_backed(cv, skills) + check_numbers_in_ledger(cv, facts)
            + check_privacy(cv, market))
