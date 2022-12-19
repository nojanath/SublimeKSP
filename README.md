# SublimeKSP

A Sublime Text plugin for working with and compiling KSP (Kontakt Script Processor) code. Works with Sublime Text versions 3 and 4.

### Changes
This fork is based on [Nils Liberg's official SublimeKSP plugin, v1.11](http://nilsliberg.se/ksp/), and supports Kontakt versions 5.6 and up. However, there are a number of additions and changes:

* Additions to the preprocessor allowing for UI arrays, new macro types and more
* Available in Package Control, which supports automatic updates
* Updates to the syntax highlighting
* Support for Creator Tools GUI Designer
* `default_syntax.py` has since been removed, since this can be set elsewhere
* See the [Added Features](https://github.com/nojanath/SublimeKSP/wiki/Added-Features) section of the [Wiki](https://github.com/nojanath/SublimeKSP/wiki) for more information

### Installation

* Install [Package Control](https://packagecontrol.io/installation)
* After installing Package Control and restarting Sublime Text:
  * Open the Command Palette from the Tools menu, or by pressing <kbd>Cmd</kbd><kbd>Shift</kbd><kbd>P</kbd> (macOS) or <kbd>Ctrl</kbd><kbd>Shift</kbd><kbd>P</kbd> (Windows)
  * Type "Install Package"
  * Type "KSP" or "Kontakt" and select "KSP (Kontakt Script Processor)"
  * Press <kbd>Enter</kbd> to install
  * Restart Sublime Text

### Manual Installation

 * To use features of SublimeKSP before official package releases, clone this repository into your `Sublime Text/Packages/` folder
 * This folder can be located in Sublime Text by selecting `Preferences > Browse Packages` from the main menu
 * Ensure that the root folder is named `SublimeKSP`
 * After pulling the latest changes, reload Sublime Text
 * If you wish to pull features without restarting Sublime Text, we recommend installing [Automatic​Package​Reloader](https://packagecontrol.io/packages/AutomaticPackageReloader)

### Documentation
See the [Wiki](https://github.com/nojanath/SublimeKSP/wiki) on Github.

### Updates
* Updates to the plugin will be automatically installed via Package Control.
* Pull requests are welcome for bugfixes/updates/changes. If you aren't familiar
with pull requests, just open an issue [here](https://github.com/nojanath/SublimeKSP/issues).

