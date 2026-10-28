"""`cv-builder ingest`: turn an existing CV, in whatever format, into text or structured data an
agent (or a person) can build the fact ledger from. Nothing here writes the CV: every fact still
goes through the ledger and the person's confirmation.

Formats: PDF, DOCX, ODT, HTML, Markdown and plain text, a LinkedIn data export (the ZIP from
"Get a copy of your data", or its folder), and JSON Resume. No extra dependencies: DOCX and ODT are
ZIP files of XML, and the PDF text comes from the gate's own extractors.
"""

from __future__ import annotations

import csv
import html.parser
import io
import json
import re
import zipfile
from pathlib import Path

from . import gate

# Fields of the LinkedIn export that are never read into anything: a CV leaves them out, and
# reading them would put them one copy-paste away from a document that gets sent.
LINKEDIN_DROPPED = {"Birth Date", "Address", "Zip Code", "Instant Messengers", "Maiden Name",
                    "Twitter Handles"}
# Each file, the key it gets, and a column its header row holds, to find that row under any
# preamble LinkedIn puts above it.
LINKEDIN_FILES = {
    "Profile.csv": ("profile", "first name"),
    "Positions.csv": ("positions", "company name"),
    "Education.csv": ("education", "school name"),
    "Skills.csv": ("skills", "name"),
    "Certifications.csv": ("certifications", "name"),
    "Languages.csv": ("languages", "name"),
    "Projects.csv": ("projects", "title"),
    "Honors.csv": ("honors", "title"),
    "Courses.csv": ("courses", "name"),
}


class _Text(html.parser.HTMLParser):
    BLOCK = {"p", "div", "br", "li", "h1", "h2", "h3", "h4", "tr", "section", "article"}

    def __init__(self):
        super().__init__()
        self.parts: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1
        elif tag in self.BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self.skip:
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def html_text(markup: str) -> str:
    parser = _Text()
    parser.feed(markup)
    return re.sub(r"\n\s*\n+", "\n\n", "".join(parser.parts)).strip()


def xml_text(xml: str, paragraph_tags: tuple[str, ...]) -> str:
    """Text of a WordprocessingML or OpenDocument body: one line per paragraph."""
    for tag in paragraph_tags:
        xml = re.sub(rf"</{tag}>", "\n", xml)
    xml = re.sub(r"<w:tab/>|<text:tab/>", "\t", xml)
    return html_text(re.sub(r"<[^>]+>", "", xml).replace("&amp;", "&"))


def pdf_text(path: Path) -> str:
    """The PDF's text as pdfminer reads it, falling back to pypdf; both ship with cv-builder."""
    for name in ("pdfminer", "pypdf"):
        text = gate.EXTRACTORS[name][0](path)
        if text.strip():
            return text
    return ""


def linkedin_export(path: Path) -> dict:
    """The CV-relevant CSV files of a LinkedIn data export, as lists of rows, with the private
    fields dropped. Works on the ZIP or on the unpacked folder."""
    out: dict = {"dropped_fields": sorted(LINKEDIN_DROPPED)}

    def rows(text: str, column: str) -> list[dict]:
        # Some exports start with a "Notes:" preamble before the header row. LinkedIn documents
        # neither the files nor their headers, so headers are matched case-insensitively.
        lines = text.splitlines()
        start = next((i for i, line in enumerate(lines)
                      if column in [c.strip().lower() for c in next(csv.reader([line]), [])]),
                     0)
        reader = csv.DictReader(io.StringIO("\n".join(lines[start:])))
        out = []
        for row in reader:
            clean = {" ".join(k.split()).title(): v for k, v in row.items() if k}
            out.append({k: v for k, v in clean.items() if k not in LINKEDIN_DROPPED})
        return out

    if path.is_dir():
        files = {p.name: p.read_text(encoding="utf-8-sig") for p in path.rglob("*.csv")}
    else:
        with zipfile.ZipFile(path) as zf:
            files = {Path(n).name: zf.read(n).decode("utf-8-sig") for n in zf.namelist()
                     if n.endswith(".csv")}
    for name, (key, column) in LINKEDIN_FILES.items():
        if name in files:
            out[key] = rows(files[name], column)
    if not any(key in out for key, _ in LINKEDIN_FILES.values()):
        raise ValueError(f"{path} holds none of the LinkedIn export files "
                         f"({', '.join(LINKEDIN_FILES)})")
    return out


MONTH = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug",
                                     "sep", "oct", "nov", "dec"], start=1)}


def linkedin_date(value: str) -> str | int | None:
    """"Mar 2021" -> "2021-03"; "2021" -> 2021; "" -> None (an empty end date means present)."""
    value = (value or "").strip()
    if not value:
        return None
    m = re.fullmatch(r"([A-Za-z]{3})[a-z]*\.? (\d{4})", value)
    if m and m.group(1).lower() in MONTH:
        return f"{m.group(2)}-{MONTH[m.group(1).lower()]:02d}"
    if re.fullmatch(r"\d{4}", value):
        return int(value)
    return value


def json_resume(data: dict) -> dict:
    """A RenderCV `cv` skeleton from a JSON Resume document (jsonresume.org): the structure only.
    Every fact in it still needs its place in the ledger before the CV states it."""
    basics = data.get("basics") or {}
    location = basics.get("location") or {}
    cv: dict = {
        "name": basics.get("name", ""),
        "headline": basics.get("label", ""),
        "location": ", ".join(p for p in (location.get("city"), location.get("countryCode")) if p),
        "email": basics.get("email", ""),
        "sections": {},
    }
    if basics.get("url"):
        cv["website"] = basics["url"]
    if basics.get("summary"):
        cv["sections"]["summary"] = [basics["summary"]]
    work = [{
        "company": w.get("name", ""), "position": w.get("position", ""),
        "start_date": (w.get("startDate") or "")[:7] or None,
        "end_date": (w.get("endDate") or "")[:7] or "present",
        "highlights": list(w.get("highlights") or []) or ([w["summary"]] if w.get("summary")
                                                          else []),
    } for w in data.get("work") or []]
    if work:
        cv["sections"]["experience"] = work
    education = [{
        "institution": e.get("institution", ""), "area": e.get("area", ""),
        "degree": e.get("studyType", ""), "start_date": (e.get("startDate") or "")[:7] or None,
        "end_date": (e.get("endDate") or "")[:7] or None,
    } for e in data.get("education") or []]
    if education:
        cv["sections"]["education"] = education
    skills = [{"label": s.get("name", ""), "details": ", ".join(s.get("keywords") or [])}
              for s in data.get("skills") or []]
    if skills:
        cv["sections"]["Skills"] = skills
    return cv


def ingest(path: Path) -> tuple[str, str]:
    """(kind, content) for one input: kind is "text" or "json"."""
    suffix = path.suffix.lower()
    if path.is_dir() or suffix == ".zip":
        return "json", json.dumps(linkedin_export(path), indent=2, ensure_ascii=False)
    if suffix == ".pdf":
        return "text", pdf_text(path)
    if suffix in (".docx", ".odt"):
        with zipfile.ZipFile(path) as zf:
            if suffix == ".docx":
                return "text", xml_text(zf.read("word/document.xml").decode("utf-8"), ("w:p",))
            return "text", xml_text(zf.read("content.xml").decode("utf-8"),
                                    ("text:p", "text:h"))
    if suffix in (".html", ".htm"):
        return "text", html_text(path.read_text(encoding="utf-8", errors="replace"))
    if suffix == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        if "basics" in data or "work" in data:
            return "json", json.dumps({"cv": json_resume(data)}, indent=2, ensure_ascii=False)
        raise ValueError(f"{path} is JSON but not a JSON Resume document")
    if suffix in (".md", ".markdown", ".txt", ".text", ".rtf"):
        text = path.read_text(encoding="utf-8", errors="replace")
        if suffix == ".rtf":
            text = re.sub(r"\\[a-z]+-?\d* ?|[{}]", "", text)
        return "text", text
    raise ValueError(f"cannot read {path.suffix or 'this'} files: convert it to PDF or DOCX")
