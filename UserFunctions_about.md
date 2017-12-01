# User python plug-ins for ksp_compiller3
allows users to build their own plug-ins in python to be executed during the compilation.

Plug-ins can be executed at the several points of the compilation process:

- at the beginning: right after all source have been imported and converted to the deque line objects
- after define macros have been solved but before macros have been
- after all macros have been iterated and expanded
- after all other preprocessor plug-ins have been handled and before optimizing and cryptography work starts

## Chages inside the source
### new userdef.py module has been added.
it consists of class UserFunсtions which handles new functions:

- `__init__` scans the source, looking for user-library path and used modules. Adds argument of userlibs_path(path) function to the sys.path. Removes lines with extension's built-in functions from the source

The following methods call the _Main(lines)_ function inside their dedicated modules and replace source by the data, returned from the _Main(lines)_ function. _lines_ here - deque, containing the source as line objects.

- `UserPreDefine` executes module, which is placed inside the library directory and has been set with `import_predefine_lib(module_name)` function inside the source.
- `UserPostDefine` executes module, which is placed inside the library directory and has been set with `import_postdefine_lib(module_name)` function inside the source.
- `UserPostMacro` executes module, which is placed inside the library directory and has been set with `import_postmacro_lib(module_name)` function inside the source.
- `UserPreCompille` executes module, which is placed inside the library directory and has been set with `import_precompille_lib(module_name)` function inside the source.

### added to the preprocesor_plugins.py:
- import statement of the userdef module
- new global object `UserLibs`, which is instance of the `UserFunсtions` class
- calls UserLibs methods inside the `pre_macro_functions` and
`post_macro_functions` 

## Examples folder
Consists of: 

- example *.py modules, which can be used as templates for future plug-in development and designed for showing the tasks, that could be solved at the every point of execution during the compilation.
- example *.ksp source demonstrating added functions. Be sure you set the proper path at the beginning of the test.ksp