"""The render shim: RenderCV must not call PyPI, and must use cvcite's package folder. The same
harness runs once without the shim's patches, as the control that proves it can see the call."""

from __future__ import annotations

import pytest
from rendercv.cli import app
from rendercv.renderer import pdf_png

from cvcite import _rendercv_shim


class RunNow:
    """Stands in for threading.Thread: runs the target at once, so the test sees the call."""

    def __init__(self, target, daemon=None):
        self.target = target

    def start(self):
        self.target()


@pytest.fixture
def pypi_calls(monkeypatch):
    calls: list[int] = []
    monkeypatch.setattr(app, "fetch_latest_version_from_pypi", lambda: calls.append(1))
    monkeypatch.setattr(app, "read_version_cache", lambda: None)
    monkeypatch.setattr(app, "write_version_cache", lambda version: None)
    monkeypatch.setattr(app.threading, "Thread", RunNow)
    # Recorded so monkeypatch restores both after the test, whatever apply_patches sets.
    monkeypatch.setattr(app, "warn_if_new_version_is_available",
                        app.warn_if_new_version_is_available)
    monkeypatch.setattr(pdf_png, "get_package_path", pdf_png.get_package_path)
    return calls


def test_unpatched_rendercv_calls_pypi(pypi_calls):
    app.warn_if_new_version_is_available()
    assert pypi_calls == [1], "control is void: the harness did not see RenderCV's PyPI call"


def test_shim_switches_off_the_pypi_call_and_sets_the_package_folder(pypi_calls, tmp_path):
    _rendercv_shim.apply_patches(tmp_path)
    app.warn_if_new_version_is_available()
    assert pypi_calls == []
    assert pdf_png.get_package_path() == tmp_path
