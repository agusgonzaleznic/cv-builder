"""Ingest every supported format, and compare a CV with a LinkedIn export. All data made up."""

from __future__ import annotations

import json
import zipfile

import pytest

from cvcite import compare, ingest

PROFILE = ("First Name,Last Name,Maiden Name,Address,Birth Date,Headline,Summary\n"
           'Robin,Example,,"1 High Street, London",1 May 1990,Data Engineering Manager,'
           "Builds data platforms.\n")
POSITIONS = ("Company Name,Title,Description,Location,Started On,Finished On\n"
             "Kestrel Freight,Data Engineering Manager,Leads the team.,London,Mar 2022,\n"
             "Brightfield Health Ltd,Data Engineer,Pipelines.,London,Jun 2018,Feb 2022\n"
             "Harbourline Retail,Data Analyst,Reports.,Manchester,Sep 2015,May 2018\n"
             "Side Project,Founder,Weekends.,Remote,Jan 2020,\n")


def export_zip(tmp_path):
    path = tmp_path / "Basic_LinkedInDataExport.zip"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("Profile.csv", PROFILE)
        zf.writestr("Positions.csv", POSITIONS)
        zf.writestr("Skills.csv", "Name\nAirflow\ndbt\n")
    return path


def test_linkedin_export_drops_private_fields(tmp_path):
    data = ingest.linkedin_export(export_zip(tmp_path))
    profile = data["profile"][0]
    assert profile["Headline"] == "Data Engineering Manager"
    assert "Birth Date" not in profile and "Address" not in profile
    assert "1 May 1990" not in json.dumps(data) and "High Street" not in json.dumps(data)
    assert [s["Name"] for s in data["skills"]] == ["Airflow", "dbt"]


def test_linkedin_export_folder_and_preamble(tmp_path):
    folder = tmp_path / "export"
    folder.mkdir()
    (folder / "Positions.csv").write_text(
        "Notes:\nThis file lists, in order, every position you added\n\n" + POSITIONS)
    positions = ingest.linkedin_export(folder)["positions"]
    assert len(positions) == 4 and positions[0]["Company Name"] == "Kestrel Freight"


def test_not_an_export(tmp_path):
    path = tmp_path / "other.zip"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("readme.txt", "hello")
    with pytest.raises(ValueError, match="none of the LinkedIn export files"):
        ingest.linkedin_export(path)


@pytest.mark.parametrize("value,expect", [
    ("Mar 2021", "2021-03"), ("2019", 2019), ("", None), ("Sept 2015", "2015-09")])
def test_linkedin_dates(value, expect):
    assert ingest.linkedin_date(value) == expect


def test_docx_odt_html_markdown(tmp_path):
    docx = tmp_path / "cv.docx"
    with zipfile.ZipFile(docx, "w") as zf:
        zf.writestr("word/document.xml", "<w:document><w:body><w:p><w:r><w:t>Robin Example"
                    "</w:t></w:r></w:p><w:p><w:r><w:t>Data &amp; platforms</w:t></w:r></w:p>"
                    "</w:body></w:document>")
    odt = tmp_path / "cv.odt"
    with zipfile.ZipFile(odt, "w") as zf:
        zf.writestr("content.xml", "<office:text><text:h>Robin Example</text:h>"
                    "<text:p>Data engineer</text:p></office:text>")
    page = tmp_path / "cv.html"
    page.write_text("<html><style>p{}</style><body><h1>Robin Example</h1><p>Data engineer</p>"
                    "<script>x()</script></body></html>")
    md = tmp_path / "cv.md"
    md.write_text("# Robin Example\n")
    assert ingest.ingest(docx) == ("text", "Robin Example\nData & platforms")
    assert ingest.ingest(odt)[1].splitlines() == ["Robin Example", "Data engineer"]
    text = ingest.ingest(page)[1]
    assert "Robin Example" in text and "x()" not in text and "p{}" not in text
    assert ingest.ingest(md) == ("text", "# Robin Example\n")


def test_pdf(render_cv, control_cv, tmp_path):
    pdf, _ = render_cv(control_cv)
    kind, text = ingest.ingest(pdf)
    assert kind == "text" and "Senior Data Engineer" in text


def test_json_resume(tmp_path):
    path = tmp_path / "resume.json"
    path.write_text(json.dumps({
        "basics": {"name": "Robin Example", "label": "Data Engineer", "email": "r@example.com",
                   "location": {"city": "London", "countryCode": "GB"}},
        "work": [{"name": "Kestrel Freight", "position": "Manager", "startDate": "2022-03-01",
                  "highlights": ["Led the team."]}],
        "skills": [{"name": "Data", "keywords": ["Airflow", "dbt"]}],
    }))
    kind, content = ingest.ingest(path)
    cv = json.loads(content)["cv"]
    assert kind == "json" and cv["location"] == "London, GB"
    assert cv["sections"]["experience"][0] == {
        "company": "Kestrel Freight", "position": "Manager", "start_date": "2022-03",
        "end_date": "present", "highlights": ["Led the team."]}
    assert cv["sections"]["Skills"][0]["details"] == "Airflow, dbt"


def test_unsupported_format(tmp_path):
    path = tmp_path / "cv.pages"
    path.write_text("x")
    with pytest.raises(ValueError, match="cannot read"):
        ingest.ingest(path)


def test_compare_roles(tmp_path):
    cv = {"sections": {"experience": [
        {"company": "Kestrel Freight", "position": "Data Engineering Manager",
         "start_date": "2022-03", "end_date": "present"},
        {"company": "Brightfield Health", "position": "Senior Data Engineer",
         "start_date": "2018-06", "end_date": "2022-02"},
        {"company": "Harbourline Retail", "position": "Data Analyst",
         "start_date": 2015, "end_date": 2018},
        {"company": "Unlisted Ltd", "position": "Intern", "start_date": 2014, "end_date": 2014},
    ]}}
    rows = {r.company: r for r in compare.compare_roles(
        cv, ingest.linkedin_export(export_zip(tmp_path)))}
    assert rows["Kestrel Freight"].status == "match"
    assert rows["Brightfield Health"].status == "differs"
    assert "title" in rows["Brightfield Health"].detail
    assert rows["Harbourline Retail"].status == "match"  # year-only dates match their year
    assert rows["Unlisted Ltd"].status == "only on the CV"
    assert rows["Side Project"].status == "only on LinkedIn"
