# SublimeKSP

A Sublime Text 3/4 plugin for working with and compiling KSP (Kontakt Script Processor) code.

### Changes
This fork is based on [Nils Liberg's official SublimeKSP plugin, v1.11](http://nilsliberg.se/ksp/), and supports all Kontakt versions.
However, there are a number of additions and changes:

* Available in Package Control, which supports automatic updates
* Updates to the syntax highlighting
* Support for Creator Tools GUI Designer
* Numerous additions to the preprocessor, allowing for UI arrays, new macro types and much more
* See the [Added Features](https://github.com/nojanath/SublimeKSP/wiki/Added-Features) section of the [Wiki](https://github.com/nojanath/SublimeKSP/wiki) for more information

### Installation

* Install [Package Control](https://packagecontrol.io/installation)
* After installing Package Control and restarting Sublime Text:
  * Open the Command Palette from the Tools menu, or by pressing <kbd>Cmd</kbd><kbd>Shift</kbd><kbd>P</kbd> (macOS) or <kbd>Ctrl</kbd><kbd>Shift</kbd><kbd>P</kbd> (Windows)
  * Type "Install Package"
  * Type "KSP" and select "KSP (Kontakt Script Processor)"
  * Press <kbd>Enter</kbd> to install
  * Restart Sublime Text

### Manual Installation

 * To use features of SublimeKSP before official package releases, clone this repository into your `Packages` folder
 * This folder can be located in Sublime Text by selecting `Preferences > Browse Packages` from the main menu
 * Ensure that the root folder is named `SublimeKSP`
 * After pulling the latest changes, reload Sublime Text
 * If you wish to pull features without restarting Sublime Text, we recommend installing [Automatic​Package​Reloader](https://packagecontrol.io/packages/AutomaticPackageReloader)

### Running From Command Line

SublimeKSP compiler can also be ran from command line, by simply executing `ksp_compiler.py` with the appropriate source (and optionally output) file path(s),
along with optional compiler switches.
For this, you need to use the manual installation of SublimeKSP, in order to have direct access to `ksp_compiler.py` file. To execute a compilation of a file,
it is as simple as typing:

```
> python ksp_compiler.py "<source-file-path>"
```

However, various compiler options from SublimeKSP's Tools menu are also available. All of them are set to false if not used,
and by including them in the command line, they are set to true:

```
ksp_compiler.py [-h] [-c] [-v] [-e] [-o] [-t] [-d] source_file [output_file]

positional arguments:
  source_file
  output_file

optional arguments:
  -h, --help                   show this help message and exit
  -c, --compact                remove indents and empty lines in compiled code
  -v, --compact_variables      shorten and obfuscate variable names in compiled code
  -e, --extra_syntax_checks    additional syntax checks during compilation
  -o, --optimize               optimize the compiled code
  -t, --add_compile_date       adds the date and time comment atop the compiled code
  -d, --combine_callbacks      combines duplicate callbacks - but not functions or macros


> python ksp_compiler.py -c -e -o "<source-file-path>" "<target-file-path"
```

### Updates
* Updates to the plugin will be automatically installed via Package Control.
* Pull requests are welcome for bugfixes/updates/changes. If you aren't familiar
with pull requests, just open an issue [here](https://github.com/nojanath/SublimeKSP/issues).

### Documentation
See the [Wiki](https://github.com/nojanath/SublimeKSP/wiki) on GitHub.