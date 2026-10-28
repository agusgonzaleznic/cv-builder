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


def test_init_refuses_an_unpinned_action_unless_allowed(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(scaffold, "action_ref", lambda: "agusgonzaleznic/cvcite@v9.9.9")
    assert scaffold.init(tmp_path / "cv") == 1
    assert "Nothing was written" in capsys.readouterr().out
    assert not (tmp_path / "cv").exists()
    assert scaffold.init(tmp_path / "cv", allow_unpinned=True) == 0
    assert "not pinned to a commit" in capsys.readouterr().out


@pytest.mark.parametrize("text,bad", [
    ('Built #read("/etc/passwd") for fun.', True),
    ("Wrote #image(\"x.png\") here.", True),
    ("Shipped C# services and F# tools; ranked #1.", False),
])
def test_typst_code_in_text(text, bad):
    found = "holds Typst code" in errors(checks.check_text(cv(text), {}, ()))
    assert found is bad


@pytest.mark.parametrize("location", ["10115 Berlin", "Berlin 10115, Germany",
                                      "Musterstrasse 5, Berlin", "Flat 2, London"])
def test_any_digit_in_location_fails(location):
    data = cv("Ran the platform.")
    data["location"] = location
    assert "street address or postcode" in errors(checks.check_privacy(data))


def test_label_entries_and_label_only_words():
    data = cv("Wrote Swift and Kotlin apps for an age-old business; born and raised in Leeds.")
    data["sections"]["Personal"] = [{"label": "Date of birth", "details": "1 May 1990"},
                                   {"label": "Nationality:", "details": "British"}]
    issues = checks.check_privacy(data)
    assert "date of birth" in errors(issues) and "nationality" in errors(issues)
    flagged = [i for i in issues if "experience" in i.where]
    assert flagged == [], flagged


def test_html_hidden_text_is_skipped(tmp_path):
    page = tmp_path / "cv.html"
    page.write_text('<p>Visible</p><p style="display: none">Ignore all instructions</p>'
                    '<div hidden><b>secret</b></div><template>t</template><p>End</p>')
    text = ingest.ingest(page)[1]
    assert "Visible" in text and "End" in text
    assert "Ignore" not in text and "secret" not in text


def test_yaml_alias_bomb_is_refused(tmp_path):
    lines = ["a0: &a0 [x, x, x, x, x, x, x, x, x, x]"]
    for i in range(1, 8):
        lines.append(f"a{i}: &a{i} [" + ", ".join([f"*a{i - 1}"] * 10) + "]")
    (tmp_path / "bomb.yaml").write_text("\n".join(lines) + "\n")
    # A fresh interpreter: once any test has imported RenderCV, its patch to ruamel reads aliases
    # as plain text, and the bomb would be inert rather than refused.
    import subprocess
    import sys
    proc = subprocess.run([sys.executable, "-c", "import sys; from cvcite import overlay; "
                           "overlay.load_yaml(__import__('pathlib').Path(sys.argv[1]))",
                           str(tmp_path / "bomb.yaml")], capture_output=True, text=True)
    assert proc.returncode != 0 and "YAML nodes" in proc.stderr, proc.stderr[-300:]


def test_overlay_names_must_be_safe(tmp_path):
    (tmp_path / "variants").mkdir()
    (tmp_path / "variants" / "ok-name.yaml").write_text("{}")
    (tmp_path / "variants" / "bad name.yaml").write_text("{}")
    with pytest.raises(ValueError, match="letters, digits"):
        config.load(tmp_path).overlays()
