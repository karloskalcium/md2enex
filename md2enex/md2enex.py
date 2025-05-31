#!/usr/bin/env python3
"""
Script to convert all markdown files in provided directory to a single .enex file for importing into Evernote
(c) 2022, 2023, 2024 Karl Brown
"""

import base64
import datetime
import hashlib
import importlib.metadata
import logging
import mimetypes
import os
import os.path
import pathlib
import platform
import subprocess
from enum import Enum
from inspect import getsourcefile
from pathlib import Path
from typing import Annotated, Optional
from urllib.parse import unquote

import pypandoc
import typer
from lxml import etree


# Enum for App Configuration Constants with functions
class Appconfig(Enum):
    APP_NAME = "md2enex"
    APP_VERSION = importlib.metadata.version("md2enex")


class Doctypes(Enum):
    ENEX_DOCTYPE = '<!DOCTYPE en-export SYSTEM "http://xml.evernote.com/pub/evernote-export4.dtd">'
    ENML_DOCTYPE = '<!DOCTYPE en-note SYSTEM "http://xml.evernote.com/pub/enml3.dtd">'


# taken from here https://dev.evernote.com/doc/articles/enml.php
# Note: embed was removed, as we process those tags and convert them to en-media
INVALID_TAGS = [
    "applet",
    "base",
    "basefont",
    "bgsound",
    "blink",
    "body",
    "button",
    "dir",
    "fieldset",
    "figcaption",  # Remove figure captions as they're not supported in ENML
    "form",
    "frame",
    "frameset",
    "head",
    "html",
    "iframe",
    "ilayer",
    "input",
    "isindex",
    "label",
    "layer",
    "legend",
    "link",
    "marquee",
    "menu",
    "meta",
    "noframes",
    "noscript",
    "object",
    "optgroup",
    "option",
    "param",
    "plaintext",
    "script",
    "select",
    "style",
    "textarea",
    "xml",
]

INVALID_ATTRIBUTES = [
    "id",
    "class",
    "controls",  # can show up in video/audio tags, but not supported in ENML
    "onclick",
    "ondblclick",
    "on*",
    "accesskey",
    "data",
    "data-cites",
    "data-emoji",
    "dynsrc",
    "tabindex",
    "aria-hidden",
]

app = typer.Typer(add_completion=False)


# stolen from https://stackoverflow.com/a/39501288/4907881
# returns creation date in seconds since Jan 1 1970 for a file in a platform-agnostic fashion
def creation_date_seconds(path_to_file) -> float:
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
            # We're probably on Linux. Try a system call
            result = subprocess.run(["stat", "-c", "%W", path_to_file], capture_output=True)
            if result.returncode == 0:
                return float(result.stdout)
            else:
                return stat.st_mtime


def create_title(file: str) -> etree.Element:
    title = Path(file).stem
    title_el = etree.Element("title")
    # just in case, per DTD, title must have no spaces or line endings
    title_el.text = title.strip()
    return title_el


def create_creation_date(file: str) -> etree.Element:
    creation_date_ts = creation_date_seconds(file)
    creation_date = enex_date_format(datetime.datetime.fromtimestamp(creation_date_ts, tz=datetime.UTC))
    created_el = etree.Element("created")
    created_el.text = creation_date
    return created_el


def create_updated_date(file: str) -> etree.Element:
    modification_date_ts = os.path.getmtime(file)
    modification_date = enex_date_format(datetime.datetime.fromtimestamp(modification_date_ts, tz=datetime.UTC))
    updated_el = etree.Element("updated")
    updated_el.text = modification_date
    return updated_el


def create_tag() -> etree.Element:
    tag_el = etree.Element("tag")
    tag_with_datetime = (
        Appconfig.APP_NAME.value + "-import" + ":" + datetime.datetime.now().isoformat(timespec="seconds")
    )
    tag_el.text = tag_with_datetime
    return tag_el


def create_note_attributes() -> etree.Element:
    note_attributes_el = etree.Element("note-attributes")
    # to make format match standard Evernote export
    note_attributes_el.text = "\n"
    return note_attributes_el


def set_xml_catalog_var():
    # Sets the XML_CATALOG_FILES variable to our catalog.xml, that points to local cache of DTDs
    # use relative path to avoid Windows error with libxml2 https://gitlab.gnome.org/GNOME/libxml2/-/issues/334
    # This will require changing the working directory during parsing
    catalog_path = "xml_cache/catalog.xml"
    logging.debug("Catalog path: " + catalog_path)
    # Set up environment variable for local catalog cache
    os.environ["XML_CATALOG_FILES"] = catalog_path


def strip_note_el(en_note_el: etree.Element):
    """Strips out invalid attributes and tags per https://dev.evernote.com/doc/articles/enml.php"""
    etree.strip_attributes(en_note_el, *INVALID_ATTRIBUTES)
    etree.strip_tags(en_note_el, *INVALID_TAGS)


def validate_note_xml(note_xml: bytes):
    # For speed, access all XML from local XML CATALOG
    working_directory = os.getcwd()
    parser = etree.XMLParser(dtd_validation=True, no_network=True)
    try:
        # Due to a libxml2 bug on windows, we need to use a relative path for the DTDs that are packaged with the tool
        # As such before doing the parsing, we change directory to the module location then change back afterwards
        # Get the path of where this module lives
        script_abs_path = os.path.dirname(os.path.abspath(getsourcefile(lambda: 0)))
        os.chdir(script_abs_path)
        etree.fromstring(note_xml, parser=parser)
    except etree.XMLSyntaxError as err:
        for error in parser.error_log:
            logging.error(error.message + "at line: " + str(error.line))

        raise err
    finally:
        os.chdir(working_directory)


def add_resources(en_note_el: etree.Element, base_dir: str) -> list:
    """Extracts and adds resources from the en-note element, converting img/video/audio/embed tags to en-media tags."""
    resources = []
    # Log the parsed XML before running XPath
    logging.debug("en_note_el XML before XPath: " + etree.tostring(en_note_el, encoding="unicode"))
    # Find all media tags (img, video, audio, embed) and convert them to en-media tags
    # Use a union of XPath expressions to find multiple tag types
    logging.debug(f"Processing media tags in en-note element from base directory: {base_dir}")
    for media_tag in en_note_el.xpath(".//img | .//video | .//audio | .//embed"):
        logging.debug("Processing media tag: " + etree.tostring(media_tag, encoding="unicode"))
        if "src" not in media_tag.attrib:
            continue

        # Decode URL-encoded path and make it relative to the markdown file
        src = unquote(media_tag.attrib["src"])
        # Make path relative to the markdown file's directory
        full_path = os.path.join(base_dir, src)
        logging.debug("Full path for media file: " + full_path)
        if not os.path.exists(full_path):
            typer.secho(f"Media file not found: {full_path}", err=True, fg="yellow")
            continue

        # Read image file
        with open(full_path, "rb") as f:
            media_data = f.read()

        # Extract mime type
        mime_type = mimetypes.guess_type(full_path)[0]
        if not mime_type:
            mime_type = "image/jpeg"  # default to jpeg if type can't be determined

        # Convert to base64
        base64_data = base64.b64encode(media_data).decode("utf-8")

        # Create resource element
        resource = etree.Element("resource")

        # Add data element with base64-encoded image
        data_el = etree.Element("data")
        data_el.text = base64_data
        data_el.set("encoding", "base64")
        resource.append(data_el)

        # Add mime type
        mime_el = etree.Element("mime")
        mime_el.text = mime_type
        resource.append(mime_el)

        # Add width and height if available
        if "width" in media_tag.attrib:
            width_el = etree.Element("width")
            width_el.text = media_tag.attrib["width"]
            resource.append(width_el)
        if "height" in media_tag.attrib:
            height_el = etree.Element("height")
            height_el.text = media_tag.attrib["height"]
            resource.append(height_el)

        # Create en-media element
        en_media = etree.Element("en-media")
        en_media.set("type", mime_type)
        # Use MD5 hash of image data as the hash attribute
        hash_value = hashlib.md5(media_data).hexdigest()
        en_media.set("hash", hash_value)

        # Set title and alt text as title attribute
        if "title" in media_tag.attrib:
            en_media.set("title", media_tag.attrib["title"])
        if "alt" in media_tag.attrib:
            en_media.set("alt", media_tag.attrib["alt"])

        # Replace media tags with en-media
        parent = media_tag.getparent()
        if parent is not None:
            parent.replace(media_tag, en_media)
            # Add resource to list
            resources.append(resource)

    # Remove figure tags but keep their content
    for figure in en_note_el.findall(".//figure"):
        parent = figure.getparent()
        if parent is not None:
            # Move all children of figure to its parent
            for child in figure:
                parent.insert(parent.index(figure), child)
            parent.remove(figure)

    # If there were issues processing any of the media tags, they will remain in the output.
    # Thus we rename them to img since that is still allowed in ENML.
    for rename_media_tag in en_note_el.xpath(".//video | .//audio | .//embed"):
        rename_media_tag.tag = "img"

    return resources


def create_note_content(file: str) -> etree.Element:
    content_text = ""
    # set hard_line_breaks here b/c the Exporter on OSX doesn't add proper line breaks in the Markdown export
    html_text = pypandoc.convert_file(
        file, to="html", format="markdown+emoji+hard_line_breaks-smart-auto_identifiers", extra_args=["--wrap=none"]
    )

    logging.debug("HTML text from pandoc conversion: " + html_text)

    for index, line in enumerate(html_text.splitlines()):
        line_trimmed = line.strip()
        # skip h1 tag from first line, if present, as this is likely the title
        if index == 0 and line_trimmed.startswith("<h1"):
            continue
        content_text += line_trimmed

    en_note_el = etree.XML(f"<en-note>{content_text}</en-note>")
    strip_note_el(en_note_el)

    # Process images and get resources
    resources = add_resources(en_note_el, os.path.dirname(file))

    en_note_bytes = etree.tostring(
        en_note_el,
        encoding="UTF-8",
        method="xml",
        xml_declaration=True,
        pretty_print=False,
        standalone=False,
        doctype=Doctypes.ENML_DOCTYPE.value,
    )

    logging.debug("EN Note XML: " + en_note_bytes.decode("utf-8"))
    validate_note_xml(en_note_bytes)

    content_el = etree.Element("content")
    content_el.text = etree.CDATA(en_note_bytes.decode("utf-8"))

    # Return both content and resources
    return content_el, resources


def process_note(file: str) -> etree.Element:
    note_el = etree.Element("note")

    note_el.append(create_title(file))
    content_el, resources = create_note_content(file)
    note_el.append(content_el)
    note_el.append(create_creation_date(file))
    note_el.append(create_updated_date(file))
    note_el.append(create_tag())
    note_el.append(create_note_attributes())

    # Add resources to note
    for resource in resources:
        note_el.append(resource)

    return note_el


# returns date in format like this: 20220817T155134Z
# as required here: http://xml.evernote.com/pub/evernote-export4.dtd
# assumes a datetime object in UTC timezone
def enex_date_format(date: datetime) -> str:
    date_str = date.strftime("%Y%m%d") + "T" + date.strftime("%H%M%S") + "Z"
    return date_str


# header material for enex format
def create_en_export() -> etree.Element:
    now = datetime.datetime.now(datetime.UTC)
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
        typer.secho("No markdown files found in " + target_directory.name, err=True, fg="red")
        raise typer.Exit(code=1)

    # ElementTree object that will contain our xml
    root = create_en_export()

    count = 0
    error_list = []
    for file in files:
        filename = str(file)
        try:
            note_xml = process_note(filename)
            root.append(note_xml)
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
        typer.secho(
            "Some files were skipped - these need to be cleaned up manually and reimported: " + str(error_list),
            err=True,
            fg="red",
        )
        raise typer.Exit(code=1)

    if count > 0:
        typer.secho("Successfully wrote " + str(count) + " markdown files to " + output_file, err=True)
    else:
        typer.secho("Error - no files written.", err=True, fg="red")
        raise typer.Exit(code=2)


def version_callback(value: bool):
    if value:
        typer.echo(Appconfig.APP_NAME.value + " (version " + Appconfig.APP_VERSION.value + ")")
        raise typer.Exit(code=0)


@app.command(context_settings={"help_option_names": ["-h", "--help"]})
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
    logging.basicConfig(level=logging.DEBUG)
    set_xml_catalog_var()
    write_enex(directory, str(output))


def main():
    app()


# needed so we can invoke within IDE
if __name__ == "__main__":
    main()
