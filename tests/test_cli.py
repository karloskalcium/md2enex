import filecmp

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
    path = "tests/test1"
    result = runner.invoke(app, [path])
    assert result.exit_code == 0
    assert "Successfully wrote 1 markdown files to export.enex" in result.stderr
    assert filecmp.cmp(f"{path}/target.enex", "export.enex")


@freeze_time(FIXED_TIME)
def test_test2():
    path = "tests/test2"
    result = runner.invoke(app, [path])
    assert result.exit_code == 0
    assert "Successfully wrote 3 markdown files to export.enex" in result.stderr
    assert filecmp.cmp(f"{path}/target.enex", "export.enex")


@freeze_time(FIXED_TIME)
def test_test3():
    path = "tests/test3"
    result = runner.invoke(app, [path])
    assert result.exit_code == 1
    assert "these need to be cleaned up manually and reimported:" in result.stderr
    assert filecmp.cmp(f"{path}/target.enex", "export.enex")


@freeze_time(FIXED_TIME)
def test_test4():
    path = "tests/test4"
    result = runner.invoke(app, [path])
    assert result.exit_code == 0
    assert "Successfully wrote 1 markdown files to export.enex" in result.stderr
    assert filecmp.cmp(f"{path}/target.enex", "export.enex")


@freeze_time(FIXED_TIME)
def test_test5():
    path = "tests/test5"
    result = runner.invoke(app, [path])
    assert result.exit_code == 0
    assert "Successfully wrote 1 markdown files to export.enex" in result.stderr
    assert filecmp.cmp(f"{path}/target.enex", "export.enex")


freezer.stop()
