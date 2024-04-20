from typer.testing import CliRunner

from md2enex.md2enex import app

runner = CliRunner()


def test_test1():
    result = runner.invoke(app, ["tests/test1"])

    assert result.exit_code == 0

    assert "Successfully wrote 1 markdown files to export.enex" in result.stdout
