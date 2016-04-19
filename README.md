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

### New Preprocessor Functions

Added to the compiler are a set of new functions that making programming in Kontakt script nicer. These functions are used near the beginning of the compiling process, before the parser. 
They work in a similar way to the C preprocessor. Syntax highlighting for these new commands has also been included. These new additions will not negatively effect any of your current programs.


* New single line comments. Use `//` to start a comment, unlike the default `{}` these comments always finish at
the end of a line. `{}` comments still work as normal. Sublime hotkey <kbd>Ctrl</kbd><kbd>/</kbd> will now use `//`, and block comment hotkey <kbd>Ctrl</kbd><kbd>Shift</kbd><kbd>/</kbd> will use `{}`.

* New constant type called define, these are always global and can be declared anywhere, even outside of 
callbacks. These are different from the original declare const, because they are substituted before macros and functions are built.
    ```
	define NUM_CONTROLS := 90
	define CONST_TEXT := "String"
    ```
    
* Use pers keyword to make a variable persistent, this would be the same as writing make_persistent(variable) in the next line:
    ```
	declare pers value
	```

* You can now always assign a value to a variable on the same line you declare it:
    ```
	declare modId := find_mod(0, "lfo")
	```

* Declare (single dimension) arrays of UI controls. Use square brackets to state the num elements. Regular const cannot be
used here, only the new define or a number. For ui_tables the first square bracket is for the number of
elements in the array, the second for the number of columns. The UI ID of each can be accessed with (using 0 as an
example) arrayName[0], or if you need the actual variable names it's arrayName0.
    ```
	declare pers ui_slider volumeSliders[40](0, 100)
	declare ui_table tables[40] [100] (2, 4, 100)
	```

* Multidimensional arrays. You can now create arrays with multiple dimensions. These can be either integers or strings. They will work with the pers keyword. Each array also has built-in constants
for the number of elements in each dimension. They follow this pattern: `<array-name>.SIZE_D1` or `<array-name>.SIZE_D2`, etc.
	```
	declare array[10, 30] // 2D array
	array[5, 6] := 100
	message(array[5, 6])
	message(array.SIZE_D1)
	declare !text[5, 5, 5] // 3D array
	```

* When you declare an array and initialise its elements on the same line, it is now optional to include
the number of elements beforehand.
    ```
	declare array[] := (79, 34, 22)
	```

* You can now declare and initialise a string array on the same line like you would an integer array.
    ```
	declare !textArray[] := ("string1", "string2")
	```

* New array type called a list. Lists are a simple construct that allow you to append values to the end
without having to specify the element index. Once declared, use the list_add() command to add values.
They can only be used in the init callback and not in loops or 'if' statements.
    ```
	declare list controlIds[]
	list_add(controlIds, get_ui_id(slider0))
	list_add(controlIds, get_ui_id(slider1))
	```

* New commands for setting UI control properties. These commands take an optional number of arguments so
you do not bloat the compiled code necessarily. There is a command for each UI type, they have been 
chosen to set the most commonly used properties of each type. There is also a command called 
set_bounds(x, y, width, height) that works for any UI type. Below is a list of all the commands and the 
arguments that each will take.
	```
	set_slider_properties(slider, default, picture, mouse_behaviour)
	set_switch_properties(switch, text, picture, text_alignment, font_type, textpos_y)
	set_label_properties(label, text, picture, text_alignment, font_type, textpos_y)
	set_menu_properties(menu, picture, font_type, text_alignment, textpos_y)
	set_table_properties(table, bar_color, zero_line_color)
	set_button_properties(button, text, picture, text_alignment, font_type, textpos_y)
	set_level_meter_properties(lev, bg_color, off_color, on_color, overload_color)
	set_waveform_properties(waveform, bar_color, zero_line_color)
	set_knob_properties(knob, text, default)
	set_bounds(volumeSlider, x, y, width, height)
	```
	
	```
	declare pers ui_switch onSwitch
	set_switch_properties(onSwitch, "", "")
	set_bounds(onSwitch, 0, 0, 20, 20)

	declare pers ui_slider volumeSliders[4](0, 1000000)
	for i := 0 to num_elements(volumeSliders) - 1
		set_slider_properties(volumeSliders[i], 500000, "Knob")
		set_bounds(10 + i * 50, 10) // We do not need to set a width and height, so they can just be left out. 
	end for
    ```

* New command for iterating a macro in a similar way to a 'for' loop. This primarily useful in situations where
Kontakt forces you to use a UI variable name instead of a UI ID number. First create a macro with 1 argument
of integer type. Then use the iterate_macro() command somewhere in your code to execute the macro a given 
number of times. The number of times is set in the same way a 'for' loop works.
    ```
	define NUM_MENUS := 5
	on init
		declare pers ui_menu menus[NUM_MENUS]
		macro addMenuItems(#n#)
			add_menu_item(menus#n#, "Item1", 0)
		end macro
		iterate_macro(addMenuItems) := 0 to NUM_MENUS - 1
	end on 
	```

* New debugging functionality. Built into the compiler is a bit of script that is activated with the command `activate_logger(directory)` in the init callback of your main script (not an imported one).
The directory is the absolute file path of folder where you wish to log messages to, for example `activate_logger("C:/")`. When activated, you can use
the function `print()` to print massages to a .nka file in this folder. If you remove the `activate_logger()` line, the program will also remove any `print()` lines. This means you can 
easily switch between debugging mode or not, and leave no footprint when it's inactive. The logger is an .nka file that can be read by a simple exe program (currently in development), 
so you can read the log in real-time.
	```
	on init
		activate_logger("C:/Users/Sam/Desktop/")
		print("Logger has begun!")
		declare ui_switch mySwitch
	end on

	on ui_control(mySwitch)
		print("Switch pressed, value: " & mySwitch)
	end on
	```
In the example about if you were to just comment out the activate_logger() line, the script would compile fine. The logger is not active, therefore the print functions will be automatically
omitted, leaving zero bloat in the output code.

* Compiled code now contains a comment with the time and date it was compiled on.
