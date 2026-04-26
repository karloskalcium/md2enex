#!/usr/bin/env python3
"""
Script to convert all markdown files in provided directory to a single .enex file for importing into Evernote
(c) 2022, 2023, 2024 Karl Brown
"""

import base64
import contextlib
import datetime
import hashlib
import importlib.metadata
import logging
import mimetypes
import os
import platform
import subprocess
from pathlib import Path
from typing import Annotated
from urllib.parse import unquote

import frontmatter
import pypandoc
import typer
from lxml import etree

# === Constants ===

APP_NAME = "md2enex"
APP_VERSION = importlib.metadata.version("md2enex")

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
    "accesskey",
    "data",
    "data-cites",
    "data-emoji",
    "dynsrc",
    "tabindex",
    "aria-hidden",
]

MODULE_DIR = Path(__file__).parent

app = typer.Typer(add_completion=False)


# === Utilities ===


def enex_date_format(date: datetime.datetime) -> str:
    """Format a UTC datetime as ``20220817T155134Z`` per the ENEX DTD."""
    return date.strftime("%Y%m%dT%H%M%SZ")


def creation_date_seconds(path_to_file) -> float:
    """
    Try to get the date that a file was created, falling back to when it was
    last modified if that isn't possible.
    See https://stackoverflow.com/a/39501288 for explanation.
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


def set_xml_catalog_var():
    """Point ``XML_CATALOG_FILES`` at the local DTD cache.

    Uses a relative path to work around a libxml2 bug on Windows
    (https://gitlab.gnome.org/GNOME/libxml2/-/issues/334); ``validate_note_xml``
    temporarily chdirs to MODULE_DIR so the path resolves at parse time.
    """
    catalog_path = "xml_cache/catalog.xml"
    logging.debug(f"Catalog path: {catalog_path}")
    os.environ["XML_CATALOG_FILES"] = catalog_path


# === Note building pipeline ===


def create_title(file: str) -> etree.Element:
    """Return a ``<title>`` element derived from the file's stem."""
    title = Path(file).stem
    title_el = etree.Element("title")
    # just in case, per DTD, title must have no spaces or line endings
    title_el.text = title.strip()
    return title_el


def create_creation_date(file: str) -> etree.Element:
    """Return a ``<created>`` element with the file's creation timestamp."""
    creation_date_ts = creation_date_seconds(file)
    creation_date = enex_date_format(datetime.datetime.fromtimestamp(creation_date_ts, tz=datetime.UTC))
    created_el = etree.Element("created")
    created_el.text = creation_date
    return created_el


def create_updated_date(file: str) -> etree.Element:
    """Return an ``<updated>`` element with the file's last-modified timestamp."""
    modification_date_ts = os.path.getmtime(file)
    modification_date = enex_date_format(datetime.datetime.fromtimestamp(modification_date_ts, tz=datetime.UTC))
    updated_el = etree.Element("updated")
    updated_el.text = modification_date
    return updated_el


def create_tag() -> etree.Element:
    """Return a ``<tag>`` element marking this import with the current UTC time."""
    tag_el = etree.Element("tag")
    now = datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds")
    tag_el.text = f"{APP_NAME}-import:{now}"
    return tag_el


def create_note_attributes() -> etree.Element:
    """Return an empty ``<note-attributes>`` element matching the standard Evernote export format."""
    note_attributes_el = etree.Element("note-attributes")
    note_attributes_el.text = "\n"
    return note_attributes_el


def extract_yaml_frontmatter(file: str) -> tuple[dict | None, str]:
    """
    Extract YAML frontmatter from a markdown file using python-frontmatter library.
    Returns a tuple of (frontmatter_dict, content_without_frontmatter)
    """
    try:
        post = frontmatter.load(file)
        return post.metadata, post.content
    except Exception as e:
        logging.warning(f"Error parsing frontmatter: {e}")
        with open(file, encoding="utf-8") as f:
            content = f.read()
        return None, content


def create_tags_from_frontmatter(frontmatter: dict) -> list[etree.Element]:
    """
    Create tag elements from YAML frontmatter.
    Looks for 'tags' or 'keywords' in the frontmatter and creates tag elements.
    """
    tag_elements = []

    tags = []
    if frontmatter:
        if "tags" in frontmatter:
            if isinstance(frontmatter["tags"], list):
                tags.extend(frontmatter["tags"])
            else:
                tags.extend([t.strip() for t in str(frontmatter["tags"]).split(",")])

        if "keywords" in frontmatter:
            if isinstance(frontmatter["keywords"], list):
                tags.extend(frontmatter["keywords"])
            else:
                tags.extend([t.strip() for t in str(frontmatter["keywords"]).split(",")])

    for tag_text in tags:
        if tag_text and tag_text.strip():
            tag_el = etree.Element("tag")
            tag_el.text = tag_text.strip()
            tag_elements.append(tag_el)

    return tag_elements


def strip_note_el(en_note_el: etree.Element):
    """Strips out invalid attributes and tags per https://dev.evernote.com/doc/articles/enml.php"""
    etree.strip_attributes(en_note_el, *INVALID_ATTRIBUTES)
    # Strip all on* event handler attributes (onclick, onload, etc.)
    # etree.strip_attributes does exact matching so a wildcard won't work
    for el in en_note_el.iter():
        for attr in list(el.attrib):
            if attr.startswith("on"):
                del el.attrib[attr]
    etree.strip_tags(en_note_el, *INVALID_TAGS)


def validate_note_xml(note_xml: bytes):
    """Validate note XML against the ENML DTD using local cached DTDs."""
    parser = etree.XMLParser(dtd_validation=True, no_network=True)
    # Due to a libxml2 bug on Windows, we need to use a relative path for the
    # DTDs that are packaged with the tool.  Temporarily chdir to the module
    # directory so the catalog's relative paths resolve correctly.
    with contextlib.chdir(MODULE_DIR):
        try:
            etree.fromstring(note_xml, parser=parser)
        except etree.XMLSyntaxError as err:
            for error in parser.error_log:
                logging.error(f"{error.message} at line: {error.line}")
            raise err


def add_resources(en_note_el: etree.Element, base_dir: str) -> list[etree.Element]:
    """Extracts and adds resources from the en-note element, converting img/video/audio/embed tags to en-media tags."""
    resources = []
    logging.debug(f"en_note_el XML before XPath: {etree.tostring(en_note_el, encoding='unicode')}")
    logging.debug(f"Processing media tags in en-note element from base directory: {base_dir}")
    for media_tag in en_note_el.xpath(".//img | .//video | .//audio | .//embed"):
        logging.debug(f"Processing media tag: {etree.tostring(media_tag, encoding='unicode')}")
        if "src" not in media_tag.attrib:
            continue

        src = unquote(media_tag.attrib["src"])
        full_path = os.path.join(base_dir, src)
        logging.debug(f"Full path for media file: {full_path}")
        if not os.path.exists(full_path):
            typer.secho(f"Media file not found: {full_path}", err=True, fg="yellow")
            continue

        with open(full_path, "rb") as f:
            media_data = f.read()

        mime_type = mimetypes.guess_type(full_path)[0]
        if not mime_type:
            mime_type = "image/jpeg"

        base64_data = base64.b64encode(media_data).decode("utf-8")

        resource = etree.Element("resource")

        data_el = etree.Element("data")
        data_el.text = base64_data
        data_el.set("encoding", "base64")
        resource.append(data_el)

        mime_el = etree.Element("mime")
        mime_el.text = mime_type
        resource.append(mime_el)

        if "width" in media_tag.attrib:
            width_el = etree.Element("width")
            width_el.text = media_tag.attrib["width"]
            resource.append(width_el)
        if "height" in media_tag.attrib:
            height_el = etree.Element("height")
            height_el.text = media_tag.attrib["height"]
            resource.append(height_el)

        en_media = etree.Element("en-media")
        en_media.set("type", mime_type)
        hash_value = hashlib.md5(media_data).hexdigest()
        en_media.set("hash", hash_value)

        if "title" in media_tag.attrib:
            en_media.set("title", media_tag.attrib["title"])
        if "alt" in media_tag.attrib:
            en_media.set("alt", media_tag.attrib["alt"])

        parent = media_tag.getparent()
        if parent is not None:
            parent.replace(media_tag, en_media)
            resources.append(resource)

    # Remove figure tags but keep their content
    for figure in en_note_el.findall(".//figure"):
        parent = figure.getparent()
        if parent is not None:
            for child in figure:
                parent.insert(parent.index(figure), child)
            parent.remove(figure)

    # If there were issues processing any of the media tags, they will remain in the output.
    # Thus we rename them to img since that is still allowed in ENML.
    for rename_media_tag in en_note_el.xpath(".//video | .//audio | .//embed"):
        rename_media_tag.tag = "img"

    return resources


def create_note_content(file: str) -> tuple[etree.Element, list[etree.Element], dict | None]:
    """Convert a markdown file to an ENML ``<content>`` element.

    Extracts YAML frontmatter, converts the remaining markdown to HTML via
    pandoc, sanitises the HTML into valid ENML, processes embedded media into
    ENEX resources, and validates the result against the ENML DTD.

    Returns ``(content_element, resources, frontmatter_dict | None)``.
    """
    frontmatter_data, markdown_content = extract_yaml_frontmatter(file)

    if frontmatter_data is not None:
        html_text = pypandoc.convert_text(
            markdown_content,
            to="html",
            format="markdown+emoji+hard_line_breaks-smart-auto_identifiers",
            extra_args=["--wrap=none"],
        )
    else:
        html_text = pypandoc.convert_file(
            file, to="html", format="markdown+emoji+hard_line_breaks-smart-auto_identifiers", extra_args=["--wrap=none"]
        )

    logging.debug(f"HTML text from pandoc conversion: {html_text}")

    lines = []
    for index, line in enumerate(html_text.splitlines()):
        stripped = line.strip()
        # skip h1 tag from first line, if present, as this is likely the title
        if index == 0 and stripped.startswith("<h1"):
            continue
        lines.append(stripped)
    content_text = "".join(lines)

    en_note_el = etree.XML(f"<en-note>{content_text}</en-note>")
    strip_note_el(en_note_el)

    resources = add_resources(en_note_el, os.path.dirname(file))

    en_note_bytes = etree.tostring(
        en_note_el,
        encoding="UTF-8",
        method="xml",
        xml_declaration=True,
        pretty_print=False,
        standalone=False,
        doctype=ENML_DOCTYPE,
    )

    logging.debug(f"EN Note XML: {en_note_bytes.decode('utf-8')}")
    validate_note_xml(en_note_bytes)

    content_el = etree.Element("content")
    content_el.text = etree.CDATA(en_note_bytes.decode("utf-8"))

    return content_el, resources, frontmatter_data


def process_note(file: str) -> etree.Element:
    """Assemble a complete ``<note>`` element from a single markdown file."""
    note_el = etree.Element("note")

    note_el.append(create_title(file))
    content_el, resources, frontmatter = create_note_content(file)
    note_el.append(content_el)
    note_el.append(create_creation_date(file))
    note_el.append(create_updated_date(file))

    note_el.append(create_tag())

    if frontmatter:
        for tag_el in create_tags_from_frontmatter(frontmatter):
            note_el.append(tag_el)

    note_el.append(create_note_attributes())

    for resource in resources:
        note_el.append(resource)

    return note_el


# === ENEX assembly and CLI ===


def create_en_export() -> etree.Element:
    """Create the top-level ``<en-export>`` element with export metadata."""
    now = datetime.datetime.now(datetime.UTC)
    now_str = enex_date_format(now)
    en_export = etree.Element("en-export")
    en_export.set("export-date", now_str)
    en_export.set("application", APP_NAME)
    en_export.set("version", APP_VERSION)
    return en_export


def write_enex(target_directory: Path, output_file: str):
    """Process all markdown files in *target_directory* and write an ENEX file.

    Raises ``typer.Exit(1)`` if the directory contains no ``.md`` files or if
    any files failed to convert, and ``typer.Exit(2)`` if zero notes were
    written despite files being present.
    """
    files = sorted(target_directory.glob("*.md"), key=lambda fn: fn.name.lower())
    if not files:
        typer.secho(f"No markdown files found in {target_directory.name}", err=True, fg="red")
        raise typer.Exit(code=1)

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
            logging.warning(f"Parsing error {e.__class__} occurred with file {filename}")
            logging.warning(e)

    tree = etree.ElementTree(root)
    tree.write(
        output_file,
        encoding="UTF-8",
        method="xml",
        pretty_print=True,
        xml_declaration=True,
        doctype=ENEX_DOCTYPE,
    )

    if error_list:
        typer.secho(
            f"Some files were skipped - these need to be cleaned up manually and reimported: {error_list}",
            err=True,
            fg="red",
        )
        raise typer.Exit(code=1)

    if count > 0:
        typer.secho(f"Successfully wrote {count} markdown files to {output_file}", err=True)
    else:
        typer.secho("Error - no files written.", err=True, fg="red")
        raise typer.Exit(code=2)


def version_callback(value: bool):
    if value:
        typer.echo(f"{APP_NAME} (version {APP_VERSION})")
        raise typer.Exit(code=0)


@app.command(context_settings={"help_option_names": ["-h", "--help"]})
def cli(
    directory: Annotated[Path, typer.Argument(exists=True, file_okay=False, dir_okay=True)],
    output: Annotated[
        Path,
        typer.Option(
            "--output",
            "-o",
            exists=False,
            dir_okay=False,
            help="Output file name. Existing file will be overwritten.",
        ),
    ] = Path("export.enex"),
    version: Annotated[
        bool | None,
        typer.Option("--version", "-v", callback=version_callback, help="Program version number"),
    ] = None,
    debug: Annotated[
        bool,
        typer.Option(
            "--debug",
            "-d",
            help="Enable debug logging",
        ),
    ] = False,
):
    """Converts all markdown files in a directory into a single .enex file for importing to Evernote."""

    logging.basicConfig(level=logging.DEBUG if debug else logging.INFO)
    set_xml_catalog_var()
    write_enex(directory, str(output))


def main():
    app()


# needed so we can invoke within IDE
if __name__ == "__main__":
    main()
