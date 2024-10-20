import os
import subprocess

import pytest
from freezegun import freeze_time
from typer.testing import CliRunner

import md2enex
from md2enex.md2enex import app

FIXED_TIME = "2024-10-18 09:00:01"
freezer = freeze_time(FIXED_TIME)
freezer.start()
runner = CliRunner(mix_stderr=False)


# Monkeypatch a fixture to fix system file time calls
@pytest.fixture(autouse=True)
def _mock_times(monkeypatch):
    """Patches system calls related to file creation and modification times"""
    CREATION_TIME = 1704110400.0  # Jan 1 2024, 12:00 UTC
    MODIFICATION_TIME = 1730419199.0  # Oct 31 2024, 23:59:59 UTC
    # Here we patch our method to just always return the same thing
    monkeypatch.setattr(md2enex.md2enex, "creation_date_seconds", lambda _: CREATION_TIME)
    # Patch mtime here
    monkeypatch.setattr(os.path, "getmtime", lambda _: MODIFICATION_TIME)


def compare_files(file1: str, file2: str):
    # easier to use diff here since it has a built in function to strip newlines
    # so that the tests work on all platforms
    result = subprocess.run(["diff", "--strip-trailing-cr", file1, file2])
    return result.returncode == 0


@freeze_time(FIXED_TIME)
def test_test1():
    path = "tests/test1"
    result = runner.invoke(app, [path])
    assert result.exit_code == 0
    assert "Successfully wrote 1 markdown files to export.enex" in result.stderr
    assert compare_files(f"{path}/target.enex", "export.enex")


@freeze_time(FIXED_TIME)
def test_test2():
    path = "tests/test2"
    result = runner.invoke(app, [path])
    assert result.exit_code == 0
    assert "Successfully wrote 3 markdown files to export.enex" in result.stderr
    assert compare_files(f"{path}/target.enex", "export.enex")


@freeze_time(FIXED_TIME)
def test_test3():
    path = "tests/test3"
    result = runner.invoke(app, [path])
    assert result.exit_code == 1
    assert "these need to be cleaned up manually and reimported:" in result.stderr
    assert compare_files(f"{path}/target.enex", "export.enex")


@freeze_time(FIXED_TIME)
def test_test4():
    path = "tests/test4"
    result = runner.invoke(app, [path])
    assert result.exit_code == 0
    assert "Successfully wrote 1 markdown files to export.enex" in result.stderr
    assert compare_files(f"{path}/target.enex", "export.enex")


@freeze_time(FIXED_TIME)
def test_test5():
    path = "tests/test5"
    result = runner.invoke(app, [path])
    assert result.exit_code == 0
    assert "Successfully wrote 1 markdown files to export.enex" in result.stderr
    assert compare_files(f"{path}/target.enex", "export.enex")


freezer.stop()
