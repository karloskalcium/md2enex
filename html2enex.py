#!/usr/bin/env python3
"""
Script to convert all HTML files in provided directory to a single .enex file for importing into Evernote
(c) 2022 Karl Brown
"""
import argparse
import datetime
import glob
import os
import os.path
from pathlib import Path
import platform
import sys
from lxml import etree


APP_NAME = 'html2enex'
APP_VERSION = '1.0'
IMPORT_TAG = APP_NAME + '-import'


# stolen from https://stackoverflow.com/a/39501288/4907881
# returns creation date in seconds since Jan 1 1970 for a file in a platform-agnostic fashion
def creation_date_seconds(path_to_file):
    """
    Try to get the date that a file was created, falling back to when it was
    last modified if that isn't possible.
    See http://stackoverflow.com/a/39501288/1709587 for explanation.
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


def process_note(file: str) -> etree.Element:
    title = Path(file).stem
    creation_date_ts = creation_date_seconds(file)
    creation_date = enex_date_format(datetime.datetime.fromtimestamp(creation_date_ts, tz=datetime.timezone.utc))
    modification_date_ts = os.path.getmtime(file)
    modification_date = enex_date_format(datetime.datetime.fromtimestamp(modification_date_ts,
                                                                         tz=datetime.timezone.utc))

    note_el = etree.Element('note')

    title_el = etree.SubElement(note_el, 'title')
    # just in case, per DTD, title must have no spaces or line endings
    title_el.text = title.strip()

    created_el = etree.SubElement(note_el, 'created')
    created_el.text = creation_date

    updated_el = etree.SubElement(note_el, 'updated')
    updated_el.text = modification_date

    # Add tags to be able to view imported notes more easily -
    # one top-level tag, and a second with a date string
    tag_1_el = etree.SubElement(note_el, 'tag')
    tag_1_el.text = IMPORT_TAG

    tag_2_el = etree.SubElement(note_el, 'tag')
    tag_2_el.text = IMPORT_TAG + ":" + datetime.datetime.now().isoformat(timespec='seconds')

    note_attributes_el = etree.SubElement(note_el, 'note-attributes')
    # to make format match standard Evernote export
    note_attributes_el.text = os.linesep

    content_text = ''
    with open(file, "r") as html_file:
        for index, line in enumerate(html_file):
            # skip h1 tag from first line, if present
            if index == 0 and line.strip().startswith('<h1'):
                continue
            content_text += line.strip()

    content_el = etree.SubElement(note_el, 'content')
    cdata_prefix = '''<?xml version="1.0" encoding="UTF-8" standalone="no"?>
    <!DOCTYPE en-note SYSTEM "http://xml.evernote.com/pub/enml2.dtd">'''
    # Create en-note by hand, as otherwise lxml will escape the content.
    # Add 6 spaces at the end to match Evernote output
    content_el.text = etree.CDATA(cdata_prefix + '<en-note>' + content_text + '</en-note>' + '      ')

    return note_el


# returns date in format like this: 20220817T155134Z
# as required here: http://xml.evernote.com/pub/evernote-export4.dtd
# assumes a datetime object in UTC timezone
def enex_date_format(date: datetime) -> str:
    date_str = date.strftime("%Y%m%d") + 'T' + date.strftime("%H%M%S") + 'Z'
    return date_str


def make_enex_doctype() -> str:
    doctype = '<!DOCTYPE en-export SYSTEM "http://xml.evernote.com/pub/evernote-export4.dtd">'
    return doctype


# header material for enex format
def make_en_export() -> etree.Element:
    now = datetime.datetime.now(datetime.timezone.utc)
    now_str = enex_date_format(now)
    en_export = etree.Element('en-export')
    en_export.set('export-date', now_str)
    en_export.set('application', APP_NAME)
    en_export.set('version', APP_VERSION)
    return en_export


def make_enex(target_directory: str, output_file: str):
    os.chdir(target_directory)
    files = glob.glob('*.html', recursive=False)
    files.extend(glob.glob('*.htm'))
    # Ensure at least one html file in directory
    if len(files) <= 0:
        sys.exit('No HTML files found in ' + target_directory)

    # ElementTree object that will contain our xml
    root = make_en_export()

    for file in files:
        root.append(process_note(file))

    tree = etree.ElementTree(root)
    doctype = make_enex_doctype()
    tree.write(output_file, encoding="UTF-8", method='xml', pretty_print=True, xml_declaration=True, doctype=doctype)


def check_dir(target_directory: str):
    if not os.path.isdir(target_directory):
        sys.exit("Invalid directory: " + target_directory)


def main(target_directory: str, output_filename: str):

    check_dir(target_directory)
    make_enex(target_directory, output_filename)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Converts all HTML files in a directory into a single .enex file for importing to Evernote.')
    parser.add_argument('-d', '--directory', required=True, action='store',
                        help='Directory to use.')
    parser.add_argument('-o', '--output', required=False, action='store',
                        default='export.enex',
                        help='Output file name. Existing file will be overwritten. Default: export.enex')
    args = parser.parse_args()
    main(args.directory, args.output)
