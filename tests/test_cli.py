import datetime
import filecmp
import os
from pathlib import Path

import pytest
from freezegun import freeze_time
from lxml import etree
from typer.testing import CliRunner

import md2enex
from md2enex.md2enex import (
    app,
    create_tags_from_frontmatter,
    enex_date_format,
    extract_yaml_frontmatter,
    strip_note_el,
)

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


# === Golden-file integration tests ===


@pytest.mark.parametrize(
    ("test_dir", "expected_count"),
    [
        ("test1", 1),
        ("test2", 3),
        ("test3", 2),
        ("test4", 1),
        ("test5", 1),
        ("test-media", 3),
    ],
)
@freeze_time(FIXED_TIME)
def test_golden_file(test_dir, expected_count):
    path = str(TESTS_DIR / test_dir)
    result = runner.invoke(app, [path])
    assert result.exit_code == 0
    assert f"Successfully wrote {expected_count} markdown files to export.enex" in result.stderr
    assert compare_files(f"{path}/target.enex", "export.enex")


# === CLI edge-case tests ===


@freeze_time(FIXED_TIME)
def test_empty_directory(tmp_path):
    result = runner.invoke(app, [str(tmp_path)])
    assert result.exit_code == 1
    assert "No markdown files found" in result.stderr


@freeze_time(FIXED_TIME)
def test_invalid_markdown(tmp_path):
    """A file that produces HTML lxml cannot parse should be logged and skipped."""
    bad_file = tmp_path / "bad.md"
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


# === Unit tests ===


def test_enex_date_format():
    dt = datetime.datetime(2024, 8, 17, 15, 51, 34, tzinfo=datetime.UTC)
    assert enex_date_format(dt) == "20240817T155134Z"


def test_strip_note_el_removes_on_attributes():
    el = etree.XML('<en-note><div onclick="alert(1)" onload="x" class="foo">text</div></en-note>')
    strip_note_el(el)
    div = el.find(".//div")
    assert "onclick" not in div.attrib
    assert "onload" not in div.attrib
    assert "class" not in div.attrib


def test_frontmatter_comma_tags():
    tags = create_tags_from_frontmatter({"tags": "a, b, c"})
    assert [t.text for t in tags] == ["a", "b", "c"]


def test_frontmatter_empty_tags_filtered():
    tags = create_tags_from_frontmatter({"tags": ["valid", "", "  "]})
    assert [t.text for t in tags] == ["valid"]


def test_frontmatter_keywords_combined():
    tags = create_tags_from_frontmatter({"tags": ["t1"], "keywords": "k1, k2"})
    assert [t.text for t in tags] == ["t1", "k1", "k2"]


def test_extract_frontmatter_invalid_yaml(tmp_path):
    bad = tmp_path / "bad.md"
    bad.write_text("---\n: :\n---\nContent here\n", encoding="utf-8")
    metadata, content = extract_yaml_frontmatter(str(bad))
    assert metadata is None
    assert "Content here" in content
