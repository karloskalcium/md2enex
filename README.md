# md2enex

[![CI](https://github.com/karloskalcium/md2enex/actions/workflows/ci.yaml/badge.svg?branch=master)](https://github.com/karloskalcium/md2enex/actions/workflows/ci.yaml)
[![LICENSE](https://img.shields.io/badge/license-MIT-blue.svg)](https://raw.githubusercontent.com/karloskalcium/md2enex/master/LICENSE)
[![PYTHON](https://img.shields.io/badge/python-3.13-orange.svg)](https://docs.python.org/3.13/index.html)

`md2enex` is a command-line tool that converts a directory of markdown files to an Evernote `.enex` export format, that can then be imported into Evernote.

## Features

- Preserves file creation dates and modification dates
- Preserves file titles
- Preserves formatting
- Supports embedded images, video, audio, and attachments
- Works on Mac, Windows, and Linux

## Install

### Install python and pipx

1. Install `python` version 3.13: [Instructions](https://www.python.org/downloads/)
1. Install `pipx`: [Instructions](https://pipx.pypa.io/stable/installation/)

### Install md2enex

1. Install `md2enex` with `pipx`:

```commandline
pipx install git+https://github.com/karloskalcium/md2enex.git
```

## Using the tool

```commandline
md2enex [-o OUTPUT_FILE] DIRECTORY
```

Note: `DIRECTORY` should be a directory containing all of the .md files you want to import. This does not work recursively, so all files must be in the top-level of the directory.

The resultant `.enex` file can be imported into Evernote using the import feature.

You can get additional help by running:

```commandline
md2enex -h
```

## Markdown formatting and conversion details

This tool uses [`pandoc`](https://pandoc.org/) to convert Markdown to HTML, and then converts that HTML to [ENML](http://xml.evernote.com/pub/enml2.dtd) (stripping some tags in the process), and then embeds this into the [ENEX](http://xml.evernote.com/pub/evernote-export4.dtd) import/export format created by Evernote.

I used [`Exporter`](http://falcon.star-lord.me/exporter/) to export notes from Apple Notes app, and since `Exporter` does not add newlines to Markdown, `md2enex` uses the [`+hard_line_breaks`](https://pandoc.org/MANUAL.html#extension-hard_line_breaks) option of `pandoc` to ensure proper line spacing. If your Markdown line spacing is correct in the source Markdown files you may want to remove that option in the `create_note_content` method.

Additionally, `Exporter` adds the title of the note as a top-level header in the note itself. This is not needed in Evernote, so if the first line of a note is a `<h1>` header, it is removed.

## Attachments Support

This tool supports embedding images and other media from your Markdown files into Evernote notes. Media are referenced in your Markdown using standard Markdown image syntax:

```markdown
![Alt text](path/to/media.jpg "Optional title")
```

The media path should be relative to the Markdown file's location. When the file is converted, the media will be properly embedded in the Evernote note as resources with the correct MIME type.

## Tags Support

This tool supports tags and keywords embedded in yaml frontmatter and converts them to evernote tags. For example see [this test file](https://raw.githubusercontent.com/karloskalcium/md2enex/refs/heads/master/tests/test4/test4.markdownyaml.md).

## Evernote import considerations

A warning: Evernote can be finicky about notes; if notes have any unknown/unsupported tags in them, they can successfully import, and then they will disappear silently at some point (perhaps when they sync to the server?). So even though this tool tries to validate the import against the Evernote DTD, to be extra safe, check the number of notes at import, and confirm that same number of notes remains in Evernote after syncing/refreshing/closing/restarting. If notes disappear, it's probably because of some strange syntax that made its way from Markdown into the generated HTML and that Evernote does not accept.

## Bugs, feature requests, or contributions

Open an [Issue](https://github.com/karloskalcium/md2enex/issues). Pull requests welcome.

You can also ask a question in the [discussions section](https://github.com/karloskalcium/md2enex/discussions).

## Other tools

- [md2evernote](https://github.com/rxrw/md2evernote)
- [Exporter - Apples Notes to markdown exporter](http://falcon.star-lord.me/exporter/)
- [Yarle - The ultimate converter of Evernote notes to Markdown](https://github.com/akosbalasko/yarle)
- [Evernote2md - Convert Evernote .enex files to Markdown](https://github.com/wormi4ok/evernote2md)

## Contributing

This project uses [uv](https://docs.astral.sh/uv/) for packaging and dependency management.

Most of the things you need to do are targets in the makefile.

- `make` to get a list of targets
- `make unit-test` to run the tests
- `make lint` to run the ruff linter
