"""The defences added after the security audit: each test plants the problem and expects the check
to stop it."""

from __future__ import annotations

import zipfile

import pytest

from cvcite import checks, cli, config, ingest, overlay, scaffold


def cv(*bullets):
    return {"name": "Test", "sections": {"experience": [
        {"company": "A", "position": "Engineer", "start_date": "2020-01", "end_date": "present",
         "highlights": list(bullets)}]}}


def errors(issues):
    return " | ".join(i.message for i in issues if i.level == "error")


@pytest.mark.parametrize("visibility", ["Private", "privat", "secret", None])
def test_unknown_visibility_fails_closed(visibility):
    facts = [{"id": "x", "text": "Revenue was GBP 90M.", "visibility": visibility}]
    issues = checks.check_numbers_in_ledger(cv("Revenue was GBP 90M."), facts)
    text = errors(issues)
    assert "must be one of" in text and "private fact" in text


def test_private_terms_never_reach_the_cv():
    facts = [{"id": "nda", "text": "Built the billing system for Northwind.",
              "visibility": "private", "terms": ["Northwind"]}]
    assert "term of a private fact" in errors(
        checks.check_numbers_in_ledger(cv("Built the billing system for northwind."), facts))
    assert "terms must be a list" in errors(checks.check_ledger(
        [{"id": "x", "text": "t", "visibility": "private", "terms": "Northwind"}]))


def test_private_facts_file_is_read(tmp_path):
    (tmp_path / "facts.yaml").write_text("facts:\n  - {id: a, text: 'x', visibility: public}\n")
    (tmp_path / "facts.private.yaml").write_text(
        "facts:\n  - {id: b, text: 'y', visibility: private, terms: [Northwind]}\n")
    facts = cli.load_facts(config.load(tmp_path))
    assert [f["id"] for f in facts] == ["a", "b"]


@pytest.mark.parametrize("merged,expect", [
    ({"design": {"theme": "mytheme"}}, "not a built-in RenderCV theme"),
    ({"rendercv_settings": {}}, "rendercv_settings"),
    ({"settings": {"render_command": {"output_folder": "/tmp"}}}, "render_command"),
])
def test_render_settings_that_run_code_or_move_files_fail(merged, expect):
    assert expect in errors(checks.check_render_settings(merged))


def test_built_in_theme_passes():
    assert checks.check_render_settings({"design": {"theme": "engineeringresumes"}}) == []


def test_street_address_in_a_bullet_warns():
    issues = checks.check_privacy(cv("Write to me at 12 Baker Street."))
    assert any(i.level == "warning" and "street address" in i.message for i in issues)


@pytest.mark.parametrize("text,expect", [
    ('[build]\nmaster = "../other/cv.yaml"\n', "inside the repository"),
    ('[build]\nbuild_dir = "/tmp/out"\n', "inside the repository"),
    ('[build]\nsend_name = "-dNOSAFER.pdf"\n', "send_name"),
    ('[gate]\nmin_contrast = 0.5\n', "min_contrast"),
])
def test_config_rejects_unsafe_values(tmp_path, text, expect):
    (tmp_path / "cvcite.toml").write_text(text)
    with pytest.raises(ValueError, match=expect):
        config.load(tmp_path)


def test_merged_yaml_has_no_comments_and_no_description(tmp_path):
    (tmp_path / "cv.yaml").write_text("# private note: salary 90k\ncv:\n  name: Test  # aside\n")
    (tmp_path / "v.yaml").write_text("_meta:\n  name: v\n  description: \"line\\ncv: {name: X}\"\n")
    variant = overlay.build_variant(tmp_path / "cv.yaml", tmp_path / "v.yaml")
    variant.dump(tmp_path / "out.yaml", "cv.yaml", "v.yaml")
    text = (tmp_path / "out.yaml").read_text()
    assert "salary" not in text and "aside" not in text and "description" not in text
    assert overlay.load_yaml(tmp_path / "out.yaml")["cv"]["name"] == "Test"


def test_linkedin_reader_keeps_only_known_columns(tmp_path):
    path = tmp_path / "export.zip"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("Profile.csv", "First Name,Headline,Passport Number,Birth Date\n"
                                   "Robin,Engineer,X123,1 May 1990\n")
    profile = ingest.linkedin_export(path)["profile"][0]
    assert profile == {"First Name": "Robin", "Headline": "Engineer"}


def test_ingest_strips_control_characters_and_tracked_deletions(tmp_path):
    docx = tmp_path / "cv.docx"
    with zipfile.ZipFile(docx, "w") as zf:
        zf.writestr("word/document.xml", "<w:p><w:r><w:t>Kept\x1b[31m</w:t></w:r>"
                    "<w:del w:id=\"1\"><w:r><w:delText>Removed</w:delText></w:r></w:del></w:p>")
    kind, text = ingest.ingest(docx)
    assert text == "Kept[31m"


def test_oversized_zip_member_is_refused(tmp_path, monkeypatch):
    path = tmp_path / "export.zip"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("Skills.csv", "Name\n" + "x\n" * 100)
    monkeypatch.setattr(ingest, "MAX_MEMBER_BYTES", 10)
    with pytest.raises(ValueError, match="larger than"):
        ingest.linkedin_export(path)


def test_init_warns_when_the_action_is_not_pinned(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(scaffold, "action_ref", lambda: "agusgonzaleznic/cvcite@v9.9.9")
    assert scaffold.init(tmp_path / "cv") == 0
    assert "not pinned to a commit" in capsys.readouterr().out
