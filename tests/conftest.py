"""Shared fixtures. Rendering is slow (a few seconds), so a test renders through `render_cv` and
each distinct CV is rendered once per session."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from cvcite import overlay, render

# A made-up CV of realistic length, built for the controls: "traffic" carries an ffi ligature,
# bold "Airflow" carries the f-l pair that kerning pushes apart, "event-driven" is a compound the
# source spells. The reading-order check is a ratio, so a CV of a few lines would magnify the one
# date each extractor places differently; this one is about as long as a short real CV.
CONTROL_CV = """\
cv:
  name: Test Person
  location: London, United Kingdom
  email: test@example.com
  sections:
    summary:
      - "Data engineer who builds pipelines that analysts trust, with a habit of writing down how things work so the next person can run them without asking."
    experience:
      - company: Example Ltd
        position: Senior Data Engineer
        location: London
        start_date: 2020-01
        end_date: present
        highlights:
          - "Moved the traffic reports to Airflow and an event-driven pipeline in two quarters."
          - "Wrote the runbooks for the on-call rotation of the data platform."
          - "Replaced hand-written exports with tested models that analysts change on their own."
          - "Set up alerts for late and empty loads, so a broken feed is noticed before the morning report."
      - company: Sample Group
        position: Data Engineer
        location: Leeds
        start_date: 2016-05
        end_date: 2019-12
        highlights:
          - "Built the nightly loads from the order system into the warehouse."
          - "Documented every table the finance team reads, with its owner and refresh time."
          - "Moved the scheduled reports from a shared desktop to a scheduler with retries."
      - company: Placeholder Retail
        position: Analyst
        location: Leeds
        start_date: 2012-09
        end_date: 2016-04
        highlights:
          - "Weekly sales and stock reports for the store managers, in SQL and spreadsheets."
          - "Cleaned the product catalogue so that every item had one category and one supplier."
    education:
      - institution: Example University
        area: Mathematics
        degree: BSc
        start_date: 2009
        end_date: 2012
design:
  theme: engineeringresumes
  page:
    size: a4
    show_top_note: false
  typography:
    alignment: {alignment}
settings:
  bold_keywords:
    - "Airflow"
"""

HYPHENATION_BAIT = (
    "Internationalization, telecommunications, interoperability, institutionalization, "
    "characterization, electroencephalography, incomprehensibilities, counterrevolutionaries, "
    "uncharacteristically, disproportionately, interdisciplinary, compartmentalization, "
    "deinstitutionalization, intercontinental, microarchitectures, overgeneralization."
)


@pytest.fixture(scope="session")
def render_cv(tmp_path_factory):
    """render_cv(yaml_text, **flags) -> (pdf, cv mapping), cached per distinct input."""
    cache: dict = {}

    def _render(text: str, *, ligatures: bool = False, kerning: bool = False):
        key = (text, ligatures, kerning)
        if key not in cache:
            folder = tmp_path_factory.mktemp("render")
            source = folder / "cv.yaml"
            source.write_text(text, encoding="utf-8")
            pdf = render.render(source, folder / "out", "CV.pdf", folder / "scratch",
                                ligatures=ligatures, kerning=kerning)
            cache[key] = (pdf, overlay.load_yaml(source)["cv"])
        return cache[key]

    return _render


@pytest.fixture(autouse=True)
def offline_action_ref(request, monkeypatch):
    """`init` looks up the release's commit on GitHub; tests stay offline except the one that
    tests the lookup itself."""
    if "real_action_ref" in request.keywords:
        return
    from cvcite import scaffold
    monkeypatch.setattr(scaffold, "action_ref",
                        lambda: "agusgonzaleznic/cvcite@" + "0" * 40 + " # v0.0.0")


@pytest.fixture
def control_cv():
    return CONTROL_CV.format(alignment="justified-with-no-hyphenation")


def has_ghostscript() -> bool:
    return shutil.which("gs") is not None


SAMPLE = Path(__file__).resolve().parent.parent / "src" / "cvcite" / "templates" / "sample"
