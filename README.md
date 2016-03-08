## SublimeKSP

A Sublime Text 3 plugin for working with and compiling Kontakt script code (KSP code).

### Installation

- Open Sublime Text 3
- Select `Preferences` -> `Browse Packages...`
- Unzip the zip-file into this folder
- If you don't want Sublime Text to use KSP mode by default
  (in case you use it for other tasks), please remove the file
  `default_syntax.py` in the unzipped folder.

### Usage

- Files with the extension ".ksp" are automatically loaded in KSP mode.
  Files with the extension ".txt" are loaded in KSP mode if the plugin
  succeeds at identifying it as a script. Please note that the detection
  currently takes place when you open a file - not when you save it
  (there's some room for improvement here). You can switch to KSP mode
  by typing [Cmd]+[Shift]+P followed by "KSP" and [Enter].
  Alternatively you can switch to KSP mode by clicking on the little drop-down menu in the status bar.
  KSP related actions/options are placed at the bottom of the Tools menu (only while in KSP mode)

- Hit [tab] to auto-complete the current name (or insert a snippet) or
  Cmd+Space to show an auto-complete menu.

- Hit Cmd+R in order to show an overview of the functions, families and callbacks.
  Start typing the name and press enter to jump to one of them.

- Hit Cmd+K (or F5 if you are using Windows) in order to Compile.
  The save_compiled_source pragma now accepts relative paths, which might be useful to know.
  If you want to customize the list of builtin functions and variables you can do so by editing the file `ksp_compiler3/ksp_builtins_data.py`.

When you open a file the plugin will examine the end-of-line characters and automatically normalize them if the previous line endings were incorrect. It will not auto-save its changes in this case, so if a newly opened file looks as if it has been modified it's because of this type of automatic normalization.
