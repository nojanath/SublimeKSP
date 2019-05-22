## Emergency Issue

ATTENTION DEVS (read if SublimeKSP is not compiling!):

If you use SublimeKSP, I pushed out 1.8.0 yesterday (5/21/2019). There seems to be an issue where compilation just hangs and stops without any error messaging. I'm not sure why this happened, since in my test repository, the compilation worked fine.

I completely uninstalled SublimeKSP from Package Control and reinstalled it, and my compilation was working again.

I don't know what caused this problem. It could be some kind of caching or storage issue in Package Control because some structural things were changed in the plugin (the options are now in a submenu in Tools).

Please let me know if reinstalling the plugin does not fix the issue!

If it is not working and you need to get up and running asap, PLEASE download the 1.7.1 version release here: https://github.com/nojanath/SublimeKSP/releases/tag/17.1

Uninstall your Package Control KSP plugin and then add this as a manual user package. Unzip the contents into <Sublime Installation Path>/Data/Packages/SublimeKSP and you will be rolled back to the previous working version.
 
The worst case scenario is that the project is rolled back to the state it was in 1.7.1 and we begin adding incremental changes again to support Kontak 6.1 features.

## SublimeKSP

A Sublime Text 3 plugin for working with and compiling Kontakt script code 
(KSP code).

### Changes
This fork is based on [Nils' official 1.11 plugin](http://nilsliberg.se/ksp/), and likewise supports Kontakt version 5.6. However there are some additions and minor changes:

* Additions to the preprocessor allowing for UI arrays, new macro types and more, see the added features section of the wiki
* Now available in Package Control which supports auto updates
* Some changes to the syntax highlighting
* default_syntax.py has been removed since this can be set elsewhere

### Installation

* Install [Package Control](https://packagecontrol.io/installation)
* After installing Package Control and restarting Sublime:
  * Open the Command Palette from the Tools menu or <kbd>Command</kbd><kbd>Shift</kbd><kbd>P</kbd> (OS X) or <kbd>Ctrl</kbd><kbd>Shift</kbd><kbd>P</kbd> (Windows)
  * Type “Install Package”
  * Type “KSP” or "Kontakt" and select "KSP (Kontakt Script Processor)"
  * Hit Enter to install
  * Restart Sublime

### Documentation
See the [Wiki](https://github.com/nojanath/SublimeKSP/wiki) on Github.

### Updates
* Updates to the plugin will be automatically installed via Package Control.
* Pull requests are welcome for errors/updates/changes. If you aren't familiar 
with pull requests, just open an [issue](https://github.com/nojanath/SublimeKSP/issues). 

