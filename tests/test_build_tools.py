"""The overlay builder, the config loader, `init` and the release packaging."""

from __future__ import annotations

from pathlib import Path

import pytest

from cv_builder import checks, config, overlay, scaffold
from cv_builder.package import package

from .conftest import SAMPLE

MASTER = """\
cv:
  name: Test
  sections:
    Skills:
      - label: Data
        details: Kafka, Spark (Structured Streaming), dbt
    experience:
      - company: A
        position: Engineer
        start_date: 2020-01
        end_date: present
        highlights:
          - "Ran Kafka in production."
          - "Wrote dbt models with tests."
"""


def write(folder: Path, name: str, text: str) -> Path:
    path = folder / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------------------- overlay

def test_overlay_merges_and_omits(tmp_path):
    master = write(tmp_path, "cv.yaml", MASTER)
    over = write(tmp_path, "variants/lean.yaml",
                 "_meta: {name: lean}\n_omit: ['dbt models']\ncv: {name: Other}\n")
    v = overlay.build_variant(master, over)
    assert v.removed == 1 and v.data["cv"]["name"] == "Other" and not v.errors
    assert len(overlay.load_yaml(master)["cv"]["sections"]["experience"][0]["highlights"]) == 2


def test_overlay_guards(tmp_path):
    master = write(tmp_path, "cv.yaml", MASTER)
    over = write(tmp_path, "variants/wide.yaml", (
        "_meta: {name: other}\n_omit: ['no such bullet']\n"
        "cv:\n  sections:\n    Skills:\n      - label: Data\n        details: Kafka, Flink\n"
        "settings:\n  bold_keywords: ['production']\n"))
    master_text = (tmp_path / "cv.yaml").read_text().replace("production.", "production; daily.")
    (tmp_path / "cv.yaml").write_text(master_text)
    v = overlay.build_variant(master, over)
    errors, warnings = " | ".join(v.errors), " | ".join(v.warnings)
    assert "'Flink'" in errors and "differs from the file name" in errors
    assert "matched nothing" in warnings and "followed by ';'" in warnings


def test_overlay_narrowing_is_allowed():
    master = {"cv": {"sections": {"Skills": [{"label": "Data", "details": "PostgreSQL 16"}]}}}
    merged = {"cv": {"sections": {"Skills": [{"label": "Data", "details": "PostgreSQL"}]}}}
    assert overlay.skills_outside_master(master, merged) == []
    master["cv"]["sections"]["Skills"][0]["details"] = "Google Cloud"
    merged["cv"]["sections"]["Skills"][0]["details"] = "Go"
    assert overlay.skills_outside_master(master, merged)


# ----------------------------------------------------------------------------------------- config

def test_config_defaults_and_codepoints(tmp_path):
    cfg = config.load(tmp_path)
    assert cfg.pages == 2 and cfg.banned == (chr(0x2014), chr(0x2015), chr(0x2E3A))
    write(tmp_path, "cv-builder.toml", '[gate]\nbanned_characters = ["U+2013"]\n')
    assert config.load(tmp_path).banned == (chr(0x2013),)


@pytest.mark.parametrize("text,expect", [
    ("[build]\npagez = 2\n", "unknown key"),
    ("[colour]\n", "unknown section"),
    ('[privacy]\nmarket = "mars"\n', "market"),
    ('[build]\nsend_name = "a/b.pdf"\n', "send_name"),
])
def test_config_rejects_typos(tmp_path, text, expect):
    write(tmp_path, "cv-builder.toml", text)
    with pytest.raises(ValueError, match=expect):
        config.load(tmp_path)


# ------------------------------------------------------------------------------------------- init

def test_init_blank_needs_filling_in(tmp_path):
    assert scaffold.init(tmp_path / "cv") == 0
    root = tmp_path / "cv"
    for name in ("AGENTS.md", "CLAUDE.md", ".gitignore", "cv.yaml", "facts.yaml",
                 "cv-builder.toml", "variants/general.yaml", ".github/workflows/cv.yml",
                 ".github/workflows/release.yml", ".github/workflows/cv-review.yml",
                 ".github/dependabot.yml"):
        assert (root / name).is_file(), name
    assert "{{ACTION_REF}}" not in (root / ".github/workflows/cv.yml").read_text()
    data = overlay.load_yaml(root / "cv.yaml")
    issues = checks.run_all(data, banned=(), facts=[], market="international")
    assert any("TODO" in i.message for i in issues if i.level == "error")


@pytest.mark.real_action_ref
def test_action_ref_pins_the_release_commit(monkeypatch):
    sha = "a" * 40

    class Done:
        stdout = f"{'b' * 40}\trefs/tags/v9.9.9\n{sha}\trefs/tags/v9.9.9^{{}}\n"

    monkeypatch.setattr(scaffold, "__version__", "9.9.9")
    monkeypatch.setattr(scaffold.subprocess, "run", lambda *a, **k: Done())
    assert scaffold.action_ref() == f"agusgonzaleznic/cv-builder@{sha} # v9.9.9"

    def offline(*a, **k):
        raise OSError("no network")

    monkeypatch.setattr(scaffold.subprocess, "run", offline)
    assert scaffold.action_ref() == "agusgonzaleznic/cv-builder@v9.9.9"
    monkeypatch.setattr(scaffold, "__version__", "9.9.10.dev0")
    assert scaffold.action_ref().startswith("agusgonzaleznic/cv-builder@main")


def test_init_refuses_a_folder_with_files(tmp_path):
    write(tmp_path, "notes.txt", "mine")
    assert scaffold.init(tmp_path) == 1
    assert not (tmp_path / "cv.yaml").exists()


def test_init_sample_passes_its_checks(tmp_path):
    assert scaffold.init(tmp_path, sample=True) == 0
    cfg = config.load(tmp_path)
    facts = overlay.load_yaml(cfg.facts_path)["facts"]
    for path in cfg.overlays():
        v = overlay.build_variant(cfg.master_path, path)
        issues = checks.run_all(v.data, banned=cfg.banned, facts=[dict(f) for f in facts],
                                market=cfg.market, today=None)
        assert not v.errors and not [i for i in issues if i.level == "error"], issues
        assert not [i for i in issues if i.level == "warning"], issues


def test_sample_is_the_shipped_sample():
    assert (SAMPLE / "cv.yaml").is_file() and (SAMPLE / "facts.yaml").is_file()


# ---------------------------------------------------------------------------------------- package

def test_package_requires_exactly_the_build(tmp_path):
    write(tmp_path, "cv-builder.toml", '[build]\nsend_name = "CV.pdf"\npages = 1\n')
    write(tmp_path, "variants/one.yaml", "_meta: {name: one}\n")
    ok, messages = package(config.load(tmp_path))
    assert not ok and "run `cv-builder build` first" in messages[0]
    for rel in ("one/CV.pdf", "one/preview_1.png", "cv-one.yaml"):
        write(tmp_path, f"build/{rel}", "x")
    ok, messages = package(config.load(tmp_path))
    assert ok, messages
    sums = (tmp_path / ".tmp/release/SHA256SUMS").read_text()
    assert "build/one/CV.pdf" in sums
    write(tmp_path, "build/one/stray.txt", "x")
    ok, messages = package(config.load(tmp_path))
    assert not ok and "unexpected" in messages[0]
