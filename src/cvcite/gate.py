"""The PDF gate: read a rendered CV the way applicant tracking systems (ATS) do, and fail it on
anything that would cost the reader a word.

Why several extractors: a PDF that looks perfect on screen can carry a text layer that one
extractor reads cleanly and another shatters into one-word lines, and an ATS may use either kind.
So the gate requires that independent extractors agree, that every bullet and entry summary of
the source survives whole and in order, and that every glyph is dark enough to read on white,
which no extractor can see: colour is paint, not text.
"""

from __future__ import annotations

import difflib
import re
import shutil
import subprocess
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

# Share of single-word lines above which a text layer counts as shattered. Measure the share of
# single-word lines, not the average words per line: an average over long lines excludes the very
# lines it is looking for, and once scored a PDF with 85% single-word lines as healthy.
SHATTER_MAX_SINGLE_WORD_RATIO = 0.35

# Below this sequence agreement two extractors read the page in a different order: usually a
# second column, a table or a float.
MIN_READING_ORDER_AGREEMENT = 0.95

# WCAG 2.2 contrast floor for normal-size text, which every line of a printed CV is. Light text is
# also what hidden-text screeners look for.
MIN_TEXT_CONTRAST = 4.5

# Em dash, horizontal bar and two-em dash. Code points, so this file holds none of them itself.
DEFAULT_BANNED = (chr(0x2014), chr(0x2015), chr(0x2E3A))

# Typst renders straight quotes and hyphens as typographic ones, so the PDF holds U+2019 where the
# YAML holds an apostrophe. Fold them before comparing, or every apostrophe reads as missing.
# Ligatures are folded too: extractors disagree about them (one reads "traffic" whole, another
# loses the "ffi" glyph), and the agreement check reports that loss separately.
PUNCT_FOLD = str.maketrans({chr(cp): plain for cp, plain in (
    (0x2018, "'"), (0x2019, "'"), (0x201A, "'"), (0x201B, "'"),        # single quotes
    (0x201C, '"'), (0x201D, '"'), (0x201E, '"'),                       # double quotes
    (0x2010, "-"), (0x2011, "-"), (0x2012, "-"), (0x2013, "-"),        # hyphens, en dash
    (0x2014, "-"), (0x2015, "-"), (0x2212, "-"),                       # em dash, bar, minus
    (0x00A0, " "), (0x2009, " "), (0x202F, " "), (0x2007, " "),        # special spaces
    (0xFB01, "fi"), (0xFB02, "fl"), (0xFB00, "ff"), (0xFB03, "ffi"),   # ligatures
    (0xFB04, "ffl"), (0xFB05, "st"), (0xFB06, "st"),
)})

MARKDOWN_LINK = re.compile(r"\[([^\]]+)\]\([^)]*\)")


def fold(text: str) -> str:
    return text.translate(PUNCT_FOLD)


# ---------------------------------------------------------------------------------- extractors

def _pypdf(pdf: Path) -> str:
    from pypdf import PdfReader
    return "\n".join(page.extract_text() or "" for page in PdfReader(str(pdf)).pages)


def _pdfminer(pdf: Path) -> str:
    from pdfminer.high_level import extract_text
    return extract_text(str(pdf))


def _ghostscript(pdf: Path) -> str:
    result = subprocess.run(
        ["gs", "-q", "-dNOPAUSE", "-dBATCH", "-dSAFER", "-sDEVICE=txtwrite",
         "-sOutputFile=-", str(pdf)],
        capture_output=True, text=True, check=True,
    )
    return result.stdout


def _pdftotext(pdf: Path) -> str:
    result = subprocess.run(["pdftotext", "-enc", "UTF-8", str(pdf), "-"],
                            capture_output=True, text=True, check=True)
    return result.stdout


def _module_available(name: str) -> Callable[[], bool]:
    def check() -> bool:
        import importlib.util
        return importlib.util.find_spec(name) is not None
    return check


EXTRACTORS: dict[str, tuple[Callable[[Path], str], Callable[[], bool]]] = {
    "pypdf": (_pypdf, _module_available("pypdf")),
    "pdfminer": (_pdfminer, _module_available("pdfminer")),
    "ghostscript": (_ghostscript, lambda: shutil.which("gs") is not None),
    "pdftotext": (_pdftotext, lambda: shutil.which("pdftotext") is not None),
}


def available_extractors() -> list[str]:
    return [name for name, (_, ok) in EXTRACTORS.items() if ok()]


# ------------------------------------------------------------------------------------ text tools

def line_end_hyphens(text: str) -> list[tuple[str, str]]:
    """Every word pair joined by a hyphen at a line end: ("event", "driven") for "event-\\ndriven"."""
    return re.findall(r"(\w{2,})-\n\s*(\w{2,})", text)


def source_compounds(source_text: str) -> set[str]:
    """The hyphenated compounds the source itself spells, lowercased."""
    return {m.lower() for m in re.findall(r"\w+(?:-\w+)+", source_text)}


def typesetter_breaks(text: str, compounds: set[str]) -> list[tuple[str, str]]:
    """Line-end hyphens the typesetter added, as opposed to a real compound wrapping at its own
    hyphen. "architec-" / "tures" fragments a keyword for every parser; "event-" / "driven" is a
    compound the source spells and is fine."""
    return [(a, b) for a, b in line_end_hyphens(text)
            if not any(f"{a}-{b}".lower() in c for c in compounds)]


def join_line_end_hyphens(text: str) -> str:
    """Rejoin a word split at a line-end hyphen, keeping the hyphen, so a wrapped compound matches
    the source and a typesetter split ("architec-tures") matches nothing."""
    return re.sub(r"(\w{2,})-\n\s*(\w{2,})", r"\1-\2\n", text)


def norm(text: str) -> list[str]:
    out = []
    for line in join_line_end_hyphens(fold(text)).splitlines():
        line = re.sub(r"\s+", " ", line).strip()
        if line:
            out.append(line)
    return out


def words(lines: list[str]) -> list[str]:
    """Tokens for comparison. Punctuation is stripped, because extractors legitimately disagree
    about it ("scalability ." against "scalability.") and that is not a reading-order problem."""
    blob = fold(" ".join(lines)).lower()
    raw = re.findall(r"[a-z0-9%&/+#]+(?:[-.'][a-z0-9%&/+#]+)*", blob)
    return [t.strip(".-'") for t in raw if t.strip(".-'")]


MONTHS = {"jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "sept", "oct", "nov",
          "dec", "january", "february", "march", "april", "june", "july", "august", "september",
          "october", "november", "december", "present"}


def is_date_token(token: str) -> bool:
    return token in MONTHS or bool(re.fullmatch(r"(19|20)\d\d", token))


def source_strings(cv: dict) -> list[str]:
    """Every bullet (`highlights`), entry `summary` and plain text entry (a summary paragraph, a
    certification line) in a RenderCV `cv` mapping: the strings that must survive whole and in
    order. Markdown links keep their text, as rendered."""
    out: list[str] = []
    for items in ((cv or {}).get("sections") or {}).values():
        for entry in items or []:
            if isinstance(entry, str):
                out.append(entry)
            elif isinstance(entry, dict):
                out.extend(str(h) for h in entry.get("highlights") or [])
                if isinstance(entry.get("summary"), str):
                    out.append(entry["summary"])
    return [MARKDOWN_LINK.sub(r"\1", s) for s in out]


# --------------------------------------------------------------------------------------- colour

def contrast_on_white(colour: str) -> float:
    """WCAG 2.2 contrast ratio of an "#rrggbb" colour against white."""
    def channel(c: int) -> float:
        c /= 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (int(colour[i:i + 2], 16) for i in (1, 3, 5))
    return 1.05 / (0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b) + 0.05)


def text_colours(pdf: Path) -> Counter:
    """Count text-showing operators by (fill colour, text render mode), read from the content
    streams. The colour is "#rrggbb" after blending any fill transparency over the white page, or
    "unchecked" for a colour space this cannot convert (CMYK, a pattern, a gradient), which fails
    the gate rather than passing it."""
    from pypdf import PdfReader
    from pypdf.generic import ContentStream, NameObject

    reader = PdfReader(str(pdf))
    counts: Counter = Counter()

    def components(name, resources) -> int | None:
        if name in ("/DeviceGray", "/DeviceRGB"):
            return 1 if name == "/DeviceGray" else 3
        spaces = resources.get("/ColorSpace")
        entry = spaces.get_object().get(name) if spaces is not None else None
        entry = entry.get_object() if entry is not None else None
        if isinstance(entry, list) and entry[0] == "/ICCBased":
            n = int(entry[1].get_object()["/N"])
            return n if n in (1, 3) else None
        return None

    def colour(state: dict) -> str:
        if state["rgb"] is None or state["alpha"] is None:
            return "unchecked"
        a = state["alpha"]
        return "#" + "".join(f"{round((a * c + 1 - a) * 255):02x}" for c in state["rgb"])

    def walk(content, resources, state: dict) -> None:
        saved = []
        for operands, op in ContentStream(content, reader).operations:
            if op == b"q":
                saved.append(dict(state))
            elif op == b"Q":
                state.update(saved.pop())
            elif op == b"cs":
                state["n"] = components(operands[0], resources)
                state["rgb"] = (0.0, 0.0, 0.0) if state["n"] else None
            elif op in (b"sc", b"scn"):
                values = [float(v) for v in operands if not isinstance(v, NameObject)]
                if state["n"] == 1 and len(values) == 1:
                    state["rgb"] = (values[0],) * 3
                elif state["n"] == 3 and len(values) == 3:
                    state["rgb"] = tuple(values)
                else:
                    state["rgb"] = None
            elif op == b"g":
                state["n"], state["rgb"] = 1, (float(operands[0]),) * 3
            elif op == b"rg":
                state["n"], state["rgb"] = 3, tuple(float(v) for v in operands)
            elif op == b"k":
                state["n"], state["rgb"] = None, None
            elif op == b"Tr":
                state["mode"] = int(operands[0])
            elif op == b"gs":
                # A graphics state the page does not define leaves the transparency unknown,
                # which fails the text it covers instead of crashing the gate.
                states = resources.get("/ExtGState")
                params = states.get_object().get(operands[0]) if states is not None else None
                if params is None:
                    state["alpha"] = None
                else:
                    alpha = params.get_object().get("/ca", state["alpha"])
                    state["alpha"] = None if alpha is None else float(alpha)
            elif op in (b"Tj", b"TJ", b"'", b'"'):
                counts[(colour(state), state["mode"])] += 1
            elif op == b"Do":
                xobject = resources["/XObject"][operands[0]].get_object()
                if xobject.get("/Subtype") == "/Form":
                    inner = xobject.get("/Resources")
                    walk(xobject, inner.get_object() if inner is not None else resources,
                         dict(state))

    for page in reader.pages:
        if page.get_contents() is not None:
            state = {"n": 1, "rgb": (0.0, 0.0, 0.0), "alpha": 1.0, "mode": 0}
            walk(page.get_contents(), page["/Resources"].get_object(), state)
    return counts


def page_count(pdf: Path) -> int:
    from pypdf import PdfReader
    return len(PdfReader(str(pdf)).pages)


# ------------------------------------------------------------------------------------- the gate

@dataclass
class GateResult:
    failures: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    pages: int = 0

    @property
    def passed(self) -> bool:
        return not self.failures

    def report(self) -> str:
        lines = list(self.notes) + [""]
        lines += [f"WARN  {w}" for w in self.warnings]
        lines += [f"FAIL  {f}" for f in self.failures]
        n_fail = sum(1 for f in self.failures if not f.startswith("    "))
        n_warn = sum(1 for w in self.warnings if not w.startswith("    "))
        if self.failures:
            lines.append(f"\nGATE FAILED ({n_fail} blocking issue(s))")
        else:
            lines.append(f"\nGATE PASSED{f' with {n_warn} warning(s)' if n_warn else ''}")
        return "\n".join(lines)


def run_gate(pdf: Path, cv: dict | None = None, *, extractors: list[str] | None = None,
             banned: tuple[str, ...] = DEFAULT_BANNED,
             min_contrast: float = MIN_TEXT_CONTRAST) -> GateResult:
    """Gate one PDF. `cv` is the RenderCV `cv` mapping the PDF was rendered from; without it the
    content-survival check is skipped and hyphenation can only warn."""
    result = GateResult()
    names = extractors or available_extractors()
    missing = [n for n in names if n not in EXTRACTORS or not EXTRACTORS[n][1]()]
    if missing:
        result.failures.append(f"extractor(s) not available: {missing}; run `cvcite doctor`")
        return result
    if len(names) < 2:
        result.failures.append(
            f"the gate needs two independent extractors and found {names}; "
            "install pdfminer.six (pip) or Ghostscript")
        return result

    raw = {n: EXTRACTORS[n][0](pdf) for n in names}
    lines = {n: norm(t) for n, t in raw.items()}
    toks = {n: words(ls) for n, ls in lines.items()}
    result.pages = page_count(pdf)
    result.notes.append(f"pages: {result.pages}")
    for n in names:
        result.notes.append(f"{n:<12} {len(lines[n])} lines, {len(toks[n])} words")

    # Banned characters, on the raw text before folding hides them.
    for ch in banned:
        hits = sorted({ln.strip() for t in raw.values() for ln in t.splitlines() if ch in ln})
        if hits:
            result.failures.append(f"{len(hits)} line(s) contain a banned character "
                                   f"U+{ord(ch):04X}:")
            result.failures.extend(f"    {h[:78]}" for h in hits[:6])

    # Hyphenation across line breaks fragments keywords. Without the source a wrapped compound
    # cannot be told from a split word, so that case only warns.
    strings = source_strings(cv) if cv else []
    compounds = source_compounds(" ".join(strings)) if cv else set()
    splits = sorted({pair for t in raw.values()
                     for pair in (typesetter_breaks(fold(t), compounds) if cv
                                  else line_end_hyphens(fold(t)))})
    if splits:
        bucket = result.failures if cv else result.warnings
        bucket.append(f"{len(splits)} word(s) hyphenated across a line break by the typesetter, "
                      "which fragments them for keyword search. Set "
                      "design.typography.alignment: justified-with-no-hyphenation")
        bucket.extend(f"    {a}-{b}  ->  '{a}-' + '{b}'" for a, b in splits[:8])

    # Shattering: a text layer broken into one-word lines parses as word soup.
    for n in names:
        wordy = [ln for ln in lines[n] if re.search(r"[A-Za-z0-9]", ln)]
        if not wordy:
            result.failures.append(f"{n} extracted no words")
            continue
        singles = [ln for ln in wordy if len(ln.split()) == 1]
        ratio = len(singles) / len(wordy)
        result.notes.append(f"{n:<12} {ratio:.0%} single-word lines")
        if ratio > SHATTER_MAX_SINGLE_WORD_RATIO:
            result.failures.append(f"{n} shattered the text layer: {ratio:.0%} of lines are a "
                                   f"single word (for example {singles[:6]})")

    # Agreement: the same words in the same order, whichever extractor an ATS uses.
    ref = names[0]
    for other in names[1:]:
        a, b = toks[ref], toks[other]
        only = (set(a) - set(b)) | (set(b) - set(a))
        if only:
            result.warnings.append(f"{ref} and {other} disagree on {len(only)} distinct "
                                   f"token(s): {sorted(only)[:8]}")
            fragments = [w for w in sorted(only) if len(w) <= 4
                         and any(w.endswith(p) or w.startswith(p) for p in ("f", "ff", "fi"))]
            if fragments:
                result.warnings.append(f"    likely lost ligature(s): fragments {fragments[:6]}")
        if a and b:
            # Words decide the verdict; dates only warn. RenderCV sets each entry's dates in a
            # right-hand column, which some extractors read after the entry's bullets. That
            # moves only the dates, and every bullet still reads whole, whereas a real column
            # or table problem interleaves the words themselves.
            agreement = difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()
            wa = [t for t in a if not is_date_token(t)]
            wb = [t for t in b if not is_date_token(t)]
            words_only = difflib.SequenceMatcher(None, wa, wb, autojunk=False).ratio()
            result.notes.append(f"reading order {ref}/{other}: {words_only:.1%} of words, "
                                f"{agreement:.1%} with dates")
            if words_only < MIN_READING_ORDER_AGREEMENT:
                result.failures.append(f"reading order differs between {ref} and {other} "
                                       f"({words_only:.1%} agreement on words): likely a column, "
                                       "table or float the parsers order differently")
            elif agreement < MIN_READING_ORDER_AGREEMENT:
                result.warnings.append(f"{other} reads the dates away from their entries "
                                       f"({agreement:.1%} agreement with dates): most parsers "
                                       "still pair them with the role, a naive one may not")

    # Content survival: every bullet and summary whole and in order, in every extractor.
    if cv:
        for n in names:
            blob = " ".join(toks[n])
            broken = [s[:78] for s in strings
                      if (probe := " ".join(words([s]))) and probe not in blob]
            if broken:
                result.failures.append(f"{len(broken)} bullet(s) or summary line(s) do not "
                                       f"appear whole in {n}'s reading (split, reordered or "
                                       "dropped):")
                result.failures.extend(f"    {s}" for s in broken[:10])

    # Colour: every glyph plainly filled, and dark enough to read on white.
    fills = text_colours(pdf)
    if not fills:
        result.failures.append("no text runs found in the content stream, so no colour was "
                               "checked: the colour reader no longer follows how this PDF "
                               "draws its text")
    per_colour: Counter = Counter()
    for (c, _mode), count in fills.items():
        per_colour[c] += count
    result.notes.append("text colours: " + ", ".join(
        f"{c} x{count}" + (f" ({contrast_on_white(c):.2f}:1)" if c.startswith("#") else "")
        for c, count in per_colour.most_common()))
    for (c, mode), count in sorted(fills.items()):
        if mode != 0:
            result.failures.append(f"{count} text run(s) in text render mode {mode}, not plainly "
                                   "filled glyphs (mode 3 is invisible text)")
        elif c == "unchecked":
            result.failures.append(f"{count} text run(s) in a colour the gate cannot check "
                                   "(CMYK, a pattern or a gradient): use an opaque hex colour")
        elif contrast_on_white(c) < min_contrast:
            result.failures.append(f"{count} text run(s) in {c}, {contrast_on_white(c):.2f}:1 "
                                   f"on white, below {min_contrast}:1")
    return result
