## SublimeKSP

A Sublime Text 3 plugin for working with and compiling Kontakt script code 
(KSP code).

### Changes
These are the notable changes from [Nils' official 1.1 plugin](http://nilsliberg.se/ksp/):

* Supports Kontakt 5.5 thanks to mk282 on vi-control.net
* default_syntax.py has been removed since this can be set elsewhere
* Now available in Package Control which supports auto updates

### Installation

* Install [Package Control](https://packagecontrol.io/installation)
* After installing Package Control and restarting Sublime:
  * Open the Command Palette from the Tools menu or <kbd>Command</kbd><kbd>Shift</kbd><kbd>P</kbd> (OS X) or <kbd>Ctrl</kbd><kbd>Shift</kbd><kbd>P</kbd> (Windows)
  * Type “Install Package”
  * Type “KSP” or "Kontakt" and select "KSP (Kontakt Script Processor)"
  * Hit Enter to install

### Manual Installation

* Open Sublime Text 3
* Select `Preferences` -> `Browse Packages...`
* Unzip the zip-file into this folder

### Documentation
There isn't documentation specifically for this plugin (yet). The best source of 
information is for Nil's [KScript Editor](http://nilsliberg.se/ksp/scripts/tutorial/editor.html). 
This plugin provides the same functionality in Sublime Text.

### Usage

* Files with the extension ".ksp" are automatically loaded in KSP mode. Files 
with the extension ".txt" are loaded in KSP mode if the plugin succeeds at 
identifying it as a script. Please note that the detection currently takes place 
when you open a file - not when you save it (there's some room for improvement 
here). 

* You can switch to KSP mode by typing [Cmd]+[Shift]+P followed by "KSP" and 
[Enter]. Alternatively you can switch to KSP mode by clicking on the little 
drop-down menu in the status bar.

* KSP related actions/options are placed at the bottom of the Tools menu (only 
while in KSP mode)

* Hit [tab] to auto-complete the current name (or insert a snippet) or Cmd+Space 
to show an auto-complete menu.

* Hit Cmd+R in order to show an overview of the functions, families and 
callbacks. Start typing the name and press enter to jump to one of them.

* Hit Cmd+K (or F5 if you are using Windows) in order to Compile. The 
save_compiled_source pragma now accepts relative paths, which might be useful to 
know.

* When you open a file the plugin will examine the end-of-line characters and 
automatically normalize them if the previous line endings were incorrect. It 
will not auto-save its changes in this case, so if a newly opened file looks as 
if it has been modified it's because of this type of automatic normalization.

### Updates
* Updates to the plugin will be automatically installed via Package Control.

* Pull requests are welcome for errors/updates/changes. If you aren't familiar 
with pull requests, just open an [issue](https://github.com/nojanath/SublimeKSP/issues). 

