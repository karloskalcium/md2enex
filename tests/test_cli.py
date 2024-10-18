from freezegun import freeze_time
from typer.testing import CliRunner

# freeze time before importing b/c of top-level time calls in md2enex
FIXED_TIME = "2024-10-18 09:00:01"
freezer = freeze_time(FIXED_TIME)
freezer.start()

from md2enex.md2enex import app  # noqa: E402

runner = CliRunner(mix_stderr=False)


@freeze_time(FIXED_TIME)
def test_test1():
    result = runner.invoke(app, ["tests/test1"])
    assert result.exit_code == 0
    assert "Successfully wrote 1 markdown files to export.enex" in result.stderr


@freeze_time(FIXED_TIME)
def test_test2():
    result = runner.invoke(app, ["tests/test2"])
    assert result.exit_code == 0
    assert "Successfully wrote 3 markdown files to export.enex" in result.stderr


def test_test3():
    result = runner.invoke(app, ["tests/test3"])
    assert result.exit_code == 1
    assert "these need to be cleaned up manually and reimported: ['tests/test3/test3.img.md']" in result.stderr


def test_test4():
    result = runner.invoke(app, ["tests/test4"])
    assert result.exit_code == 0
    assert "Successfully wrote 1 markdown files to export.enex" in result.stderr


def test_test5():
    result = runner.invoke(app, ["tests/test5"])
    assert result.exit_code == 0
    assert "Successfully wrote 1 markdown files to export.enex" in result.stderr


freezer.stop()
