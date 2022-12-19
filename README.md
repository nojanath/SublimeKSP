# SublimeKSP

A Sublime Text 3 plugin for working with and compiling KSP (Kontakt Script Processor) code.

### Changes
This fork is based on [Nils Liberg's official SublimeKSP plugin, v1.11](http://nilsliberg.se/ksp/), and likewise supports Kontakt versions 5.6 and up. However, there are a number of additions and changes:

* Additions to the preprocessor allowing for UI arrays, new macro types and more
* Available in Package Control, which supports automatic updates
* Updates to the syntax highlighting
* Support for Creator Tools GUI Designer
* default_syntax.py has been removed since this can be set elsewhere
* See the [Added Features](https://github.com/nojanath/SublimeKSP/wiki/Added-Features) section of the [Wiki](https://github.com/nojanath/SublimeKSP/wiki) for more information

### Installation

* Install [Package Control](https://packagecontrol.io/installation)
* After installing Package Control and restarting Sublime Text 3:
  * Open the Command Palette from the Tools menu, or by hitting <kbd>Cmd</kbd><kbd>Shift</kbd><kbd>P</kbd> (macOS) or <kbd>Ctrl</kbd><kbd>Shift</kbd><kbd>P</kbd> (Windows)
  * Type "Install Package"
  * Type "KSP" or "Kontakt" and select "KSP (Kontakt Script Processor)"
  * Hit <kbd>Enter</kbd> to install
  * Restart Sublime Text 3

### Manual Installation

 * To use features of SublimeKSP before official package releases, clone this repo into your `Sublime Text 3/Packages/KSP (Kontakt Script Processor)`  
 * This directory can be located in Sublime Text by selecting `Preferences > Browse Packages`  
 * Ensure that the root directory is `KSP (Kontakt Script Processor)`
 * After pulling the latest changes reload Sublime Text
 * If you wish to pull features without restarting Sublime Text, I recommend installing [Automatic​Package​Reloader](https://packagecontrol.io/packages/AutomaticPackageReloader)

### Documentation
See the [Wiki](https://github.com/nojanath/SublimeKSP/wiki) on Github.

### Updates
* Updates to the plugin will be automatically installed via Package Control.
* Pull requests are welcome for bugfixes/updates/changes. If you aren't familiar 
with pull requests, just open an issue [here](https://github.com/nojanath/SublimeKSP/issues). 

