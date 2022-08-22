# md2enex
`md2enex` is a Python command-line tool that converts a directory of HTML files to an evernote .enex export format. It preserves file titles, creation dates and modification dates.

This can be used to import files from other tools into Evernote.

## Importing markdown
Because the ENML format is somewhat constrained and this code is fairly simple, 
it is suggested to export to markdown, then use pandoc to turn markdown into HTML.

## Install and local development

### Clone repo
  `$ git clone https://github.com/karloskalcium/md2enex.git`

### Create and configure virtual environment.
Make sure you have the correct version of python. [Pyenv](https://github.com/pyenv/pyenv) manages python versions.
  1. `pyenv install 3.10.6` (use version in `.python-version`)
  2. Make sure to configure your shell's environment for pyenv following instructions in step 2
    [here](https://github.com/pyenv/pyenv#basic-github-checkout).
  3. Once this is done, start a new shell and run `pyenv version` and `python --version` in the terminal from the root directory of the project, both should read `3.10.6`

#### *nix / OSX
 ```
  $ make python-install
  $ source ENV/bin/activate
 ```

### Run the tool
```
  $ ./md2enex.py -d <directory> -o <output filename>
```

## Bugs, feature requests, or contributions
Open an [Issue](https://github.com/karloskalcium/md2enex/issues). Pull requests welcome.
