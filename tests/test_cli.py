import filecmp
import os
from pathlib import Path

import pytest
from freezegun import freeze_time
from typer.testing import CliRunner

import md2enex
from md2enex.md2enex import app

FIXED_TIME = "2024-10-18 09:00:01"
TESTS_DIR = Path(__file__).parent

runner = CliRunner()


@pytest.fixture(autouse=True)
def _mock_times(monkeypatch):
    """Patches system calls related to file creation and modification times"""
    CREATION_TIME = 1704110400.0  # Jan 1 2024, 12:00 UTC
    MODIFICATION_TIME = 1730419199.0  # Oct 31 2024, 23:59:59 UTC
    monkeypatch.setattr(md2enex.md2enex, "creation_date_seconds", lambda _: CREATION_TIME)
    monkeypatch.setattr(os.path, "getmtime", lambda _: MODIFICATION_TIME)


@pytest.fixture(autouse=True)
def _mock_version(monkeypatch):
    """Patches the version to a fixed value for testing"""
    monkeypatch.setattr(md2enex.md2enex, "APP_VERSION", "0.3")


def compare_files(file1: str, file2: str) -> bool:
    return filecmp.cmp(file1, file2, shallow=False)


@freeze_time(FIXED_TIME)
def test_test1():
    path = str(TESTS_DIR / "test1")
    result = runner.invoke(app, [path])
    assert result.exit_code == 0
    assert "Successfully wrote 1 markdown files to export.enex" in result.stderr
    assert compare_files(f"{path}/target.enex", "export.enex")


@freeze_time(FIXED_TIME)
def test_test2():
    path = str(TESTS_DIR / "test2")
    result = runner.invoke(app, [path])
    assert result.exit_code == 0
    assert "Successfully wrote 3 markdown files to export.enex" in result.stderr
    assert compare_files(f"{path}/target.enex", "export.enex")


@freeze_time(FIXED_TIME)
def test_test3():
    path = str(TESTS_DIR / "test3")
    result = runner.invoke(app, [path])
    assert result.exit_code == 0
    assert "Successfully wrote 2 markdown files to export.enex" in result.stderr
    assert compare_files(f"{path}/target.enex", "export.enex")


@freeze_time(FIXED_TIME)
def test_test4():
    path = str(TESTS_DIR / "test4")
    result = runner.invoke(app, [path])
    assert result.exit_code == 0
    assert "Successfully wrote 1 markdown files to export.enex" in result.stderr
    assert compare_files(f"{path}/target.enex", "export.enex")


@freeze_time(FIXED_TIME)
def test_test5():
    path = str(TESTS_DIR / "test5")
    result = runner.invoke(app, [path])
    assert result.exit_code == 0
    assert "Successfully wrote 1 markdown files to export.enex" in result.stderr
    assert compare_files(f"{path}/target.enex", "export.enex")


@freeze_time(FIXED_TIME)
def test_testmedia():
    path = str(TESTS_DIR / "test-media")
    result = runner.invoke(app, [path])
    assert result.exit_code == 0
    assert "Successfully wrote 3 markdown files to export.enex" in result.stderr
    assert compare_files(f"{path}/target.enex", "export.enex")


@freeze_time(FIXED_TIME)
def test_empty_directory(tmp_path):
    result = runner.invoke(app, [str(tmp_path)])
    assert result.exit_code == 1
    assert "No markdown files found" in result.stderr


@freeze_time(FIXED_TIME)
def test_invalid_markdown(tmp_path):
    """A file that produces HTML lxml cannot parse should be logged and skipped."""
    bad_file = tmp_path / "bad.md"
    # Unclosed CDATA / raw XML that will trip the ENML DTD validator
    bad_file.write_text("<en-note><invalid-toplevel-tag></en-note>", encoding="utf-8")
    result = runner.invoke(app, [str(tmp_path)])
    assert result.exit_code != 0


@freeze_time(FIXED_TIME)
def test_missing_media(tmp_path):
    """A markdown file referencing a non-existent image should warn but still succeed."""
    md_file = tmp_path / "note.md"
    md_file.write_text("![alt](nonexistent.png)\n", encoding="utf-8")
    result = runner.invoke(app, [str(tmp_path)])
    assert "Media file not found" in result.stderr
