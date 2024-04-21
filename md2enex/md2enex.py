#!/usr/bin/env python3
"""
Script to convert all markdown files in provided directory to a single .enex file for importing into Evernote
(c) 2022, 2023, 2024 Karl Brown
"""

import datetime
import importlib.metadata
import logging
import os
import os.path
import pathlib
import platform
from enum import Enum
from inspect import getsourcefile
from pathlib import Path
from typing import Annotated, Optional

import pypandoc
import typer
from lxml import etree


# Enum for App Configuration Constants with functions
class Appconfig(Enum):
    APP_NAME = "md2enex"
    APP_VERSION = importlib.metadata.version("md2enex")


class Doctypes(Enum):
    ENEX_DOCTYPE = '<!DOCTYPE en-export SYSTEM "http://xml.evernote.com/pub/evernote-export4.dtd">'
    ENML_DOCTYPE = '<!DOCTYPE en-note SYSTEM "http://xml.evernote.com/pub/enml2.dtd">'


IMPORT_TAG_WITH_DATETIME = (
    Appconfig.APP_NAME.value + "-import" + ":" + datetime.datetime.now().isoformat(timespec="seconds")
)

app = typer.Typer(add_completion=False)


# stolen from https://stackoverflow.com/a/39501288/4907881
# returns creation date in seconds since Jan 1 1970 for a file in a platform-agnostic fashion
def creation_date_seconds(path_to_file):
    """
    Try to get the date that a file was created, falling back to when it was
    last modified if that isn't possible.
    See https://stackoverflow.com/a/39501288/1709587 for explanation.
    """
    if platform.system() == "Windows":
        return os.path.getctime(path_to_file)
    else:
        stat = os.stat(path_to_file)
        try:
            return stat.st_birthtime
        except AttributeError:
            # We're probably on Linux. No easy way to get creation dates here,
            # so we'll settle for when its content was last modified.
            return stat.st_mtime


def create_title(file: str) -> etree.Element:
    title = Path(file).stem
    title_el = etree.Element("title")
    # just in case, per DTD, title must have no spaces or line endings
    title_el.text = title.strip()
    return title_el


def create_creation_date(file: str) -> etree.Element:
    creation_date_ts = creation_date_seconds(file)
    creation_date = enex_date_format(datetime.datetime.fromtimestamp(creation_date_ts, tz=datetime.timezone.utc))
    created_el = etree.Element("created")
    created_el.text = creation_date
    return created_el


def create_updated_date(file: str) -> etree.Element:
    modification_date_ts = os.path.getmtime(file)
    modification_date = enex_date_format(
        datetime.datetime.fromtimestamp(modification_date_ts, tz=datetime.timezone.utc)
    )
    updated_el = etree.Element("updated")
    updated_el.text = modification_date
    return updated_el


def create_tag() -> etree.Element:
    tag_el = etree.Element("tag")
    tag_el.text = IMPORT_TAG_WITH_DATETIME
    return tag_el


def create_note_attributes() -> etree.Element:
    note_attributes_el = etree.Element("note-attributes")
    # to make format match standard Evernote export
    note_attributes_el.text = os.linesep
    return note_attributes_el


def set_xml_catalog_var():
    # Sets the XML_CATALOG_FILES variable to our catalog.xml, that points to local cache of DTDs
    # use relative path to avoid Windows error with libxml2 https://gitlab.gnome.org/GNOME/libxml2/-/issues/334
    # This will require changing the working directory during parsing
    catalog_path = "xml_cache/catalog.xml"
    logging.debug("Catalog path: " + catalog_path)
    # Set up environment variable for local catalog cache
    os.environ["XML_CATALOG_FILES"] = catalog_path


def strip_note_el(en_note_el: etree.Element) -> etree.Element:
    etree.strip_attributes(en_note_el, "id", "class", "data", "data-cites")


def validate_note_xml(note_xml: bytes):
    # For speed, access all XML from local XML CATALOG
    try:
        # Due to a libxml2 bug on windows, we need to use a relative path for the DTDs that are packaged with the tool
        # As such before doing the parsing, we change directory to the module location then change back afterwards
        working_directory = os.getcwd()
        # Get the path of where this module lives
        script_abs_path = os.path.dirname(os.path.abspath(getsourcefile(lambda: 0)))
        os.chdir(script_abs_path)
        parser = etree.XMLParser(dtd_validation=True, no_network=True)
        etree.fromstring(note_xml, parser=parser)
    except etree.XMLSyntaxError as err:
        for error in parser.error_log:
            logging.error(error.message + "at line: " + str(error.line))

        raise err
    finally:
        os.chdir(working_directory)


def check_invalid_tags(en_note_el: etree.Element):
    if len(en_note_el.findall(".//img")) or len(en_note_el.findall(".//figure")):
        raise etree.LxmlSyntaxError("Found image tags - skipping...")


def create_note_content(file: str) -> etree.Element:
    content_text = ""
    # set hard_line_breaks here b/c the Exporter on OSX doesn't add proper line breaks in the Markdown export
    html_text = pypandoc.convert_file(
        file, "html", format="markdown+hard_line_breaks-smart-auto_identifiers", extra_args=["--wrap=none"]
    )
    for index, line in enumerate(html_text.splitlines()):
        line_trimmed = line.strip()
        # skip h1 tag from first line, if present, as this is likely the title
        if index == 0 and line_trimmed.startswith("<h1"):
            continue
        content_text += line_trimmed

    en_note_el = etree.XML(f"<en-note>{content_text}</en-note>")
    strip_note_el(en_note_el)
    en_note_bytes = etree.tostring(
        en_note_el,
        encoding="UTF-8",
        method="xml",
        xml_declaration=True,
        pretty_print=False,
        standalone=False,
        doctype=Doctypes.ENML_DOCTYPE.value,
    )

    validate_note_xml(en_note_bytes)
    check_invalid_tags(en_note_el)

    content_el = etree.Element("content")
    content_el.text = etree.CDATA(en_note_bytes.decode("utf-8"))

    return content_el


def process_note(file: str) -> etree.Element:
    note_el = etree.Element("note")

    note_el.append(create_title(file))
    note_el.append(create_note_content(file))
    note_el.append(create_creation_date(file))
    note_el.append(create_updated_date(file))
    note_el.append(create_tag())
    note_el.append(create_note_attributes())

    return note_el


# returns date in format like this: 20220817T155134Z
# as required here: http://xml.evernote.com/pub/evernote-export4.dtd
# assumes a datetime object in UTC timezone
def enex_date_format(date: datetime) -> str:
    date_str = date.strftime("%Y%m%d") + "T" + date.strftime("%H%M%S") + "Z"
    return date_str


# header material for enex format
def create_en_export() -> etree.Element:
    now = datetime.datetime.now(datetime.timezone.utc)
    now_str = enex_date_format(now)
    en_export = etree.Element("en-export")
    en_export.set("export-date", now_str)
    en_export.set("application", Appconfig.APP_NAME.value)
    en_export.set("version", Appconfig.APP_VERSION.value)
    return en_export


def write_enex(target_directory: pathlib.Path, output_file: str):
    files = sorted(target_directory.glob("*.md"), key=lambda fn: str.lower(fn.name))
    # Ensure at least one markdown file in directory
    if len(files) <= 0:
        typer.echo("No markdown files found in " + target_directory.name, err=True)
        raise typer.Exit(code=1)

    # ElementTree object that will contain our xml
    root = create_en_export()

    count = 0
    error_list = []
    for file in files:
        filename = str(file)
        try:
            root.append(process_note(filename))
            count += 1
        except (etree.LxmlError, ValueError) as e:
            error_list.append(filename)
            logging.warning("Parsing error " + str(e.__class__) + " occurred with file " + filename)
            logging.warning(e)

    tree = etree.ElementTree(root)
    tree.write(
        output_file,
        encoding="UTF-8",
        method="xml",
        pretty_print=True,
        xml_declaration=True,
        doctype=Doctypes.ENEX_DOCTYPE.value,
    )

    if len(error_list) > 0:
        logging.warning(
            "Some files were skipped - these need to be cleaned up manually and reimported: " + str(error_list)
        )

    if count > 0:
        typer.echo("Successfully wrote " + str(count) + " markdown files to " + output_file)
    else:
        logging.error("Error - no files written.")
        raise typer.Exit(code=2)


def version_callback(value: bool):
    if value:
        typer.echo(Appconfig.APP_NAME.value + " (version " + Appconfig.APP_VERSION.value + ")")
        raise typer.Exit(code=0)


@app.command()
def cli(
    directory: Annotated[Path, typer.Argument(exists=True, file_okay=False, dir_okay=True, path_type=pathlib.Path)],
    output: Annotated[
        Path,
        typer.Option(
            "--output",
            "-o",
            exists=False,
            dir_okay=False,
            path_type=pathlib.Path,
            help="Output file name. Existing file will be overwritten.",
        ),
    ] = "export.enex",
    version: Annotated[
        Optional[bool],  # noqa: UP007
        typer.Option("--version", "-v", callback=version_callback, help="Program version number"),
    ] = None,
):
    """Converts all markdown files in a directory into a single .enex file for importing to Evernote."""
    # logging.basicConfig(level=logging.DEBUG)
    set_xml_catalog_var()
    write_enex(directory, str(output))


def main():
    app()


# needed so we can invoke within IDE
if __name__ == "__main__":
    main()
