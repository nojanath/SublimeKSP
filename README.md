## SublimeKSP BETA

A Sublime Text 3 plugin for working with and compiling Kontakt script code (KSP code).
This version of SublimeKSP includes all the features from the latest Beta versions of Kontakt. The informations contained in this repo are confidential and shall not be shared with anyone who is not a member of the Alpha/Beta Team.

### Changes
This fork is based on [Nils' official 1.11 plugin](http://nilsliberg.se/ksp/), and likewise supports Kontakt version 5.6. However there are some additions and minor changes:

* Additions to the preprocessor allowing for UI arrays, new macro types and more, see the added features section of the wiki
* Now available in Package Control which supports auto updates
* Some changes to the syntax highlighting
* default_syntax.py has been removed since this can be set elsewhere

### Installation

This fork cannot be installed via PackageControl, thus needs to be installed and updated manually.

#### GitHub Desktop

* From the main page of the repository, in the upper right corner, click on the green button <kbd>Clone or download</kbd>
* Click on <kbd>Open in Desktop</kbd>. You will be brought to GitHub Desktop.
* On GitHub Desktop, click on <kbd>Choose</kbd> to change the destination path
* The destination path must be the "Packages" folder of your Sublime Text installation. On Mac, the path is located at `~/Library/Application Support/Sublime Text 3/Packages/`
* Restart Sublime Text 
* Click on the lower-right corner of the window and select "KSP" from the dropdown menu

#### Sourcetree, command-line and other Git GUI applications

* From the main page of the repository, in the upper right corner, click on the green button <kbd>Clone or download</kbd>
* Copy the URL shown on the box that appears
* Paste the URL in your application for cloning
* Change the destination path. The destination path must be the "Packages" folder of your Sublime Text installation. On Mac, the path is located at `~/Library/Application Support/Sublime Text 3/Packages/`. If you are unable to change the destination path from the application you are using, simply clone the repository to the default folder, move it manually to the "Packages" folder and relocate it from the application
* Restart Sublime Text 
* Click on the lower-right corner of the window and select "KSP" from the dropdown menu

### Documentation
See the [Wiki](https://github.com/nojanath/SublimeKSP/wiki) on Github.

### Updates
* Updates to the plugin will be automatically installed via Package Control.
* Pull requests are welcome for errors/updates/changes. If you aren't familiar 
with pull requests, just open an [issue](https://github.com/nojanath/SublimeKSP/issues). 

