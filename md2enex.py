#!/usr/bin/env python3
"""
Script to convert all markdown files in provided directory to a single .enex file for importing into Evernote
(c) 2022 Karl Brown
"""
import argparse
import datetime
import glob
import os
import os.path
from pathlib import Path
import platform
import pypandoc
import sys
from lxml import etree


APP_NAME = 'md2enex'
APP_VERSION = '1.0'
IMPORT_TAG_WITH_DATETIME = APP_NAME + '-import' + ":" + datetime.datetime.now().isoformat(timespec='seconds')
ENEX_DOCTYPE = '<!DOCTYPE en-export SYSTEM "http://xml.evernote.com/pub/evernote-export4.dtd">'
ENML_PREFIX = '''<?xml version="1.0" encoding="UTF-8" standalone="no"?>
                 <!DOCTYPE en-note SYSTEM "http://xml.evernote.com/pub/enml2.dtd">'''


# stolen from https://stackoverflow.com/a/39501288/4907881
# returns creation date in seconds since Jan 1 1970 for a file in a platform-agnostic fashion
def creation_date_seconds(path_to_file):
    """
    Try to get the date that a file was created, falling back to when it was
    last modified if that isn't possible.
    See https://stackoverflow.com/a/39501288/1709587 for explanation.
    """
    if platform.system() == 'Windows':
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
    title_el = etree.Element('title')
    # just in case, per DTD, title must have no spaces or line endings
    title_el.text = title.strip()
    return title_el


def create_creation_date(file: str) -> etree.Element:
    creation_date_ts = creation_date_seconds(file)
    creation_date = enex_date_format(datetime.datetime.fromtimestamp(creation_date_ts, tz=datetime.timezone.utc))
    created_el = etree.Element('created')
    created_el.text = creation_date
    return created_el


def create_updated_date(file: str) -> etree.Element:
    modification_date_ts = os.path.getmtime(file)
    modification_date = enex_date_format(datetime.datetime.fromtimestamp(modification_date_ts,
                                                                         tz=datetime.timezone.utc))
    updated_el = etree.Element('updated')
    updated_el.text = modification_date
    return updated_el


def create_tag() -> etree.Element:
    tag_el = etree.Element('tag')
    tag_el.text = IMPORT_TAG_WITH_DATETIME
    return tag_el


def create_note_attributes() -> etree.Element:
    note_attributes_el = etree.Element('note-attributes')
    # to make format match standard Evernote export
    note_attributes_el.text = os.linesep
    return note_attributes_el


def create_note_content(file: str) -> etree.Element:
    content_text = ''
    # set hard_line_breaks here b/c the Exporter on OSX doesn't add proper line breaks in the Markdown export
    html_text = pypandoc.convert_file(file, 'html', format='markdown+hard_line_breaks', extra_args=['--wrap=none'])
    for index, line in enumerate(html_text.splitlines()):
        line_trimmed = line.strip()
        # skip h1 tag from first line, if present, as this is likely the title
        if index == 0 and line_trimmed.startswith('<h1'):
            continue
        if line_trimmed.startswith('<figure') or line_trimmed.startswith('<img'):
            print("Skipped " + file + " because of unsupported figure/image tags.")
            return None
        content_text += line_trimmed

    # Create en-note by hand, as otherwise lxml will escape the content.
    # Add 6 spaces at the end to match Evernote output
    enml = ENML_PREFIX + '<en-note>' + content_text + '</en-note>' + '      '

    content_el = etree.Element('content')
    content_el.text = etree.CDATA(enml)
    return content_el


def process_note(file: str) -> etree.Element:
    print('processing ' + file, flush=True)
    note_el = etree.Element('note')

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
    date_str = date.strftime("%Y%m%d") + 'T' + date.strftime("%H%M%S") + 'Z'
    return date_str


# header material for enex format
def create_en_export() -> etree.Element:
    now = datetime.datetime.now(datetime.timezone.utc)
    now_str = enex_date_format(now)
    en_export = etree.Element('en-export')
    en_export.set('export-date', now_str)
    en_export.set('application', APP_NAME)
    en_export.set('version', APP_VERSION)
    return en_export


def make_enex(target_directory: str, output_file: str):
    os.chdir(target_directory)
    files = sorted(glob.glob('*.md', recursive=False), key=str.lower)
    # Ensure at least one markdown file in directory
    if len(files) <= 0:
        sys.exit('No markdown files found in ' + target_directory)

    # ElementTree object that will contain our xml
    root = create_en_export()

    for count, file in enumerate(files, start=1):
        root.append(process_note(file))

    tree = etree.ElementTree(root)
    tree.write(output_file, encoding="UTF-8", method='xml', pretty_print=True, xml_declaration=True, doctype=ENEX_DOCTYPE)

    print('Successfully wrote ' + str(count) + ' markdown files to ' + os.path.join(target_directory, output_file))


def check_dir(target_directory: str):
    if not os.path.isdir(target_directory):
        sys.exit("Invalid directory: " + target_directory)


def main(target_directory: str, output_filename: str):
    check_dir(target_directory)
    make_enex(target_directory, output_filename)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Converts all markdown files in a directory into a single .enex file for importing to Evernote.')
    parser.add_argument('-d', '--directory', required=True, action='store',
                        help='Directory to use.')
    parser.add_argument('-o', '--output', required=False, action='store',
                        default='export.enex',
                        help='Output file name. Existing file will be overwritten. Default: export.enex')
    args = parser.parse_args()
    main(args.directory, args.output)
