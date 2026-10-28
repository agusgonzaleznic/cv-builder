"""The gate, with a control for every check: each planted defect must fail it, and the clean
render must pass. A check that cannot fail proves nothing."""

from __future__ import annotations

from collections import Counter

import pytest
from pypdf import PdfReader, PdfWriter
from pypdf.generic import ContentStream, DictionaryObject, FloatObject, NameObject

from cvcite import gate

from .conftest import CONTROL_CV, HYPHENATION_BAIT, has_ghostscript

TEXT_SHOW = {b"Tj", b"TJ", b"'", b'"'}


def blocking(result: gate.GateResult) -> str:
    return "\n".join(result.failures)


def test_clean_render_passes(render_cv, control_cv):
    pdf, cv = render_cv(control_cv)
    result = gate.run_gate(pdf, cv)
    assert result.passed, result.report()
    assert result.pages == 1


def test_banned_character_fails(render_cv):
    text = CONTROL_CV.format(alignment="justified-with-no-hyphenation").replace(
        "in two quarters.", "in two quarters " + chr(0x2014) + " on time.")
    pdf, cv = render_cv(text)
    result = gate.run_gate(pdf, cv)
    assert "banned character U+2014" in blocking(result)


@pytest.mark.skipif(not has_ghostscript(), reason="the ligature loss shows in Ghostscript")
def test_ligatures_on_fail(render_cv, control_cv):
    """Control for turning ligatures off: with them on, Ghostscript loses "traffic"."""
    pdf, cv = render_cv(control_cv, ligatures=True)
    result = gate.run_gate(pdf, cv)
    assert "ghostscript's reading" in blocking(result), result.report()


def test_kerning_on_fails(render_cv, control_cv):
    """Control for turning kerning off: with it on, pdfminer reads bold "Airflow" as two words."""
    pdf, cv = render_cv(control_cv, kerning=True)
    result = gate.run_gate(pdf, cv)
    assert "pdfminer's reading" in blocking(result), result.report()


def test_typesetter_hyphenation_fails(render_cv):
    text = CONTROL_CV.format(alignment="justified").replace(
        "Wrote the runbooks for the on-call rotation of the data platform.", HYPHENATION_BAIT)
    pdf, cv = render_cv(text)
    raw = gate.EXTRACTORS["pypdf"][0](pdf)
    assert gate.line_end_hyphens(gate.fold(raw)), "control is void: Typst hyphenated nothing"
    result = gate.run_gate(pdf, cv)
    assert "hyphenated across a line break" in blocking(result)


def test_wrapped_compound_is_not_a_split():
    text = "an event-\ndriven pipeline and architec-\ntures"
    assert gate.typesetter_breaks(text, {"event-driven"}) == [("architec", "tures")]


# ------------------------------------------------------------------------------ colour controls

def first_colour_index(ops) -> int:
    """The first fill colour that is not black: the section titles of the control CV."""
    for i, (operands, op) in enumerate(ops):
        if op == b"scn" and len(operands) == 3 and any(float(v) > 0.01 for v in operands):
            return i
    raise AssertionError("the render has no coloured text to edit")


def edited(pdf, tmp_path, name, edit, add_alpha=False):
    writer = PdfWriter(clone_from=PdfReader(str(pdf)))
    page = writer.pages[0]
    if add_alpha:
        resources = page["/Resources"].get_object()
        resources[NameObject("/ExtGState")] = DictionaryObject(
            {NameObject("/GSa"): DictionaryObject({NameObject("/ca"): FloatObject(0.2)})})
    stream = ContentStream(page.get_contents(), writer)
    stream.operations = edit(list(stream.operations))
    page.replace_contents(stream)
    out = tmp_path / f"{name}.pdf"
    writer.write(str(out))
    return out


def before_first_text(ops, extra):
    i = next(i for i, (_, op) in enumerate(ops) if op in TEXT_SHOW)
    return ops[:i] + [extra] + ops[i:]


@pytest.fixture
def coloured(render_cv):
    text = CONTROL_CV.format(alignment="justified-with-no-hyphenation").replace(
        "  typography:", '  colors:\n    section_titles: "#1d4f91"\n  typography:')
    return render_cv(text)


def test_coloured_render_passes(coloured):
    pdf, cv = coloured
    result = gate.run_gate(pdf, cv)
    assert result.passed, result.report()
    assert any("#1d4f91" in n for n in result.notes)


@pytest.mark.parametrize("name,expect", [
    ("light", "below 4.5:1"),
    ("invisible", "render mode 3"),
    ("alpha", "below 4.5:1"),
    ("cmyk", "cannot check"),
    ("undefined-state", "cannot check"),
])
def test_colour_controls_fail(coloured, tmp_path, name, expect):
    pdf, cv = coloured

    def light(ops):
        i = first_colour_index(ops)
        ops[i] = ([FloatObject(0.8)] * 3, b"scn")
        return ops

    def cmyk(ops):
        i = first_colour_index(ops)
        ops[i] = ([FloatObject(0), FloatObject(0.8), FloatObject(0.9), FloatObject(0.1)], b"k")
        return ops

    edits = {
        "light": (light, False),
        "invisible": (lambda ops: before_first_text(ops, ([FloatObject(3)], b"Tr")), False),
        "alpha": (lambda ops: before_first_text(ops, ([NameObject("/GSa")], b"gs")), True),
        "cmyk": (cmyk, False),
        "undefined-state": (lambda ops: before_first_text(ops, ([NameObject("/Nope")], b"gs")),
                            False),
    }
    edit, add_alpha = edits[name]
    control = edited(pdf, tmp_path, name, edit, add_alpha)
    result = gate.run_gate(control, cv)
    assert expect in blocking(result), result.report()


def test_empty_colour_census_fails(coloured, monkeypatch):
    pdf, cv = coloured
    monkeypatch.setattr(gate, "text_colours", lambda _pdf: Counter())
    assert "no text runs found" in blocking(gate.run_gate(pdf, cv))


# ------------------------------------------------------------------- extractor-level controls

def with_extractor(monkeypatch, name, transform):
    real, available = gate.EXTRACTORS[name]
    monkeypatch.setitem(gate.EXTRACTORS, name, (lambda pdf: transform(real(pdf)), available))


def test_shattered_text_fails(render_cv, control_cv, monkeypatch):
    pdf, cv = render_cv(control_cv)
    with_extractor(monkeypatch, "pdfminer", lambda t: "\n".join(t.split()))
    assert "shattered the text layer" in blocking(gate.run_gate(pdf, cv))


def test_reading_order_fails(render_cv, control_cv, monkeypatch):
    pdf, cv = render_cv(control_cv)
    with_extractor(monkeypatch, "pdfminer", lambda t: "\n".join(reversed(t.splitlines())))
    assert "reading order differs" in blocking(gate.run_gate(pdf, cv))


def test_dropped_bullet_fails(render_cv, control_cv, monkeypatch):
    pdf, cv = render_cv(control_cv)
    with_extractor(monkeypatch, "pypdf", lambda t: t.replace("runbooks", "playbooks"))
    assert "do not appear whole in pypdf's reading" in blocking(gate.run_gate(pdf, cv))


def test_one_extractor_is_not_enough(render_cv, control_cv):
    pdf, cv = render_cv(control_cv)
    assert "needs two independent extractors" in blocking(
        gate.run_gate(pdf, cv, extractors=["pypdf"]))
