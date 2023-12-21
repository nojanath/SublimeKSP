import sublime
import sublime_plugin

import traceback
import io
import os
import re
import sys
import threading
import urllib, tarfile, json, shutil
import webbrowser
import xml.etree.ElementTree as ET

from datetime import datetime
from subprocess import call

try:
    import winsound
except Exception:
    pass

sys.path.append(os.path.dirname(__file__))
sys.path.append(os.path.join(os.path.dirname(__file__), 'compiler'))

import ksp_ast
import ksp_compiler
import preprocessor_plugins
import utils

last_compiler = None
sublime_version = int(sublime.version())

pragma_save_src_re = r'\{\s*\#pragma\s+save_compiled_source\s+(.*)\}'
import_path_re = r'\s*import\s+[\"\'](.*)[\"\']'
save_src_compiled_re = re.compile(pragma_save_src_re)
pragma_and_import_re = re.compile(r'%s|%s' % (pragma_save_src_re, import_path_re))

class CompileKspCommand(sublime_plugin.ApplicationCommand):
    '''Compile the KSP file or files'''

    def __init__(self):
        sublime_plugin.ApplicationCommand.__init__(self)
        self.thread = None
        self.last_filename = None

    def is_enabled(self):
        # only show the command when a file with KSP syntax highlighting is visible

        view = sublime.active_window().active_view()

        if view:
            return 'KSP.sublime-syntax' in view.settings().get('syntax', '')

    def run(self, *args, **kwargs):
        # find the view containing the code to compile
        view = sublime.active_window().active_view()

        # wait until any previous thread is finished
        if self.thread and self.thread.is_alive():
            # if attempting to compile a different file, bail out, otherwise abort current compile and start a new one
            if view.file_name() != self.last_filename:
                utils.log_message('Another compilation is in progress! Please wait until it is finished.')
                return False
            else:
                self.thread.stop()

        if kwargs.get('recompile', None) and self.last_filename:
            view = CompileKspThread.find_view_by_filename(self.last_filename)

        open_views = [view]

        if kwargs.get('compile_all_open', None):
            open_views = view.window().views()
            open_views = [view for view in open_views if re.search(r'source\.ksp',view.scope_name(0))]

        self.thread = CompileKspThread(open_views)
        self.thread.start()
        self.last_filename = view.file_name()


class RecompileKsp(sublime_plugin.ApplicationCommand):
    '''Recompile the most recently compiled file'''

    def is_enabled(self):
        # only show the command when a file with KSP syntax highlighting is visible

        view = sublime.active_window().active_view()

        if view:
            return 'KSP.sublime-syntax' in view.settings().get('syntax', '')

    def run(self, *args):
        sublime.active_window().run_command('compile_ksp', {'recompile': True})


class CompileAllOpenKspCommand(sublime_plugin.ApplicationCommand):
    '''Compile all scripts open in the current Sublime Text window'''

    def run(self, *args):
        sublime.active_window().run_command('compile_ksp', {'compile_all_open': True})


class GetSound:
    dir = None

    def __init__(self):
        self.dir = os.path.join(sublime.packages_path(), 'KSP (Kontakt Script Processor)', 'sounds')

    def play(self, **kwargs):
        sound_path = os.path.join(self.dir, '{}.wav'.format(kwargs['command']))

        if sublime.platform() == "windows":
            if os.path.isfile(sound_path):
                winsound.PlaySound(sound_path, winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
        elif sublime.platform() == "osx":
            if os.path.isfile(sound_path):
                call(["afplay", "-v", str(1), sound_path])
        else:
            if os.path.isfile(sound_path):
                call(["aplay", sound_path])


class CompileKspThread(threading.Thread):
    def __init__(self, open_views):
        threading.Thread.__init__(self)

        self.base_path = None
        self.compiler = None
        self.open_views = open_views
        self.current_view = None
        self.compile_all_open = False

        if len(open_views) > 1:
            self.compile_all_open = True

    def stop(self):
        if self.compiler:
            self.compiler.abort_compilation()

    @classmethod
    def find_view_by_filename(cls, filename, base_path = None):
        if filename is None:
            return sublime.active_window().active_view()

        if not os.path.isabs(filename) and base_path:
            filename = os.path.join(base_path, filename)

        for window in sublime.windows():
            for view in window.views():
                if view.file_name() and view.file_name() == filename:
                    return view

        return None

    def compile_handle_error(self, error_msg, error_lineno, error_filename):
        view = CompileKspThread.find_view_by_filename(error_filename, self.base_path)

        if view:
            sublime.active_window().focus_view(view)

            if error_lineno is not None:
                pos = view.text_point(error_lineno, 0)
                line_region = view.line(sublime.Region(pos, pos))
                selection = view.sel()
                view.show(line_region)
                selection.clear()
                selection.add(line_region)

        utils.log_message('Error - compilation aborted!')
        sublime.error_message(error_msg)
        sublime.status_message('')

    def run(self):
        global last_compiler

        for view in self.open_views:
            self.current_view = view
            code = view.substr(sublime.Region(0, view.size()))
            filepath = view.file_name()

            if filepath:
                self.base_path = os.path.dirname(filepath)
            else:
                self.base_path = None

            settings = sublime.load_settings("KSP.sublime-settings")

            compact = settings.get('ksp_compact_output', False)
            compact_variables = settings.get('ksp_compact_variables', False)
            check = settings.get('ksp_extra_checks', True)
            optimize = settings.get('ksp_optimize_code', False)
            combine_callbacks = settings.get('ksp_combine_callbacks', False)
            sanitize_exit_command = settings.get('ksp_sanitize_exit_command', True)
            add_compiled_date_comment = settings.get('ksp_add_compiled_date', True)
            should_play_sound = settings.get('ksp_play_sound', False)

            error_msg = None
            error_lineno = None
            error_filename = filepath # path to main script

            sound_utility = GetSound()

            if self.compile_all_open and not save_src_compiled_re.search(code):
                if filepath == None:
                    filepath = 'untitled'

                utils.log_message('Error: No output path was specified for \'%s\' - skipping compilation for this script!' % filepath)

                continue

            try:
                t1 = datetime.now()

                if self.compile_all_open:
                    utils.log_message('Compiling \'%s\', script %s of %s...' % (filepath, self.open_views.index(view) + 1, len(self.open_views)))
                else:
                    if filepath == None:
                        filepath = 'untitled'

                    utils.log_message('Compiling \'%s\'...' % filepath)

                self.compiler = ksp_compiler.KSPCompiler(code,
                                                         self.base_path,
                                                         compact                   = compact,
                                                         compact_variables         = compact_variables,
                                                         extra_syntax_checks       = check,
                                                         combine_callbacks         = combine_callbacks,
                                                         optimize                  = optimize and check,
                                                         sanitize_exit_command     = sanitize_exit_command,
                                                         add_compiled_date_comment = add_compiled_date_comment)

                if self.compiler.compile(callback = utils.compile_on_progress):
                    last_compiler = self.compiler
                    code = self.compiler.compiled_code
                    code = code.replace('\r', '')
                    num_output_files = len(self.compiler.output_files)

                    delta = utils.calc_time_diff(datetime.now() - t1)

                    if num_output_files > 0:
                        paths = []

                        for f in self.compiler.output_files:
                            if not os.path.isabs(f):
                                f = os.path.join(self.base_path, f)

                            with io.open(f, 'w', encoding = 'latin-1') as o:
                                o.write(code)

                            paths.append(f)

                        utils.log_message('Successfully compiled in %s! Compiled code was saved to:' % delta)

                        for p in paths:
                            utils.log_message('    %s' % p)
                    else:
                        utils.log_message('Successfully compiled in %s! The code is copied to the clipboard, ready to be pasted into Kontakt.' % delta)
                        sublime.set_clipboard(code)

            except ksp_ast.ParseException as e:
                error_msg = str(e)
                line_object = self.compiler.lines[e.lineno]

                if line_object:
                    error_lineno = line_object.lineno-1
                    error_filename = line_object.filename

                if line_object:
                    error_msg = re.sub(r'line (\d+)', 'line %s' % line_object.lineno, error_msg)

            except ksp_compiler.ParseException as e:
                error_lineno = e.line.lineno-1
                error_filename = e.line.filename
                error_msg = e.message

            except Exception as e:
                error_msg = str(e)
                error_msg = ''.join(traceback.format_exception(*sys.exc_info()))

            if error_msg:
                self.compile_handle_error(error_msg, error_lineno, error_filename)
            else:
                if should_play_sound and self.compiler.abort_requested == False:
                    sound_utility.play(command = "finished")

    def description(self, *args):
        return 'Compiled KSP'


# **********************************************************************************************


from compiler.ksp_builtins import keywords, all_builtins, functions, function_signatures, functions_with_forced_parentheses

builtins = set(functions.keys()) | set([x[1:] for x in all_builtins]) | all_builtins | keywords
functions, builtins = set(functions), set(builtins)

builtin_compl_funcs = []
builtin_compl_vars = []
builtin_snippets = []

magic_control_and_event_pars = []

def plugin_loaded():
    # copy our built in sound to the unmanaged packages folder, so we can io.open it at runtime
    try:
        res = sublime.load_binary_resource('Packages/KSP (Kontakt Script Processor)/sounds/finished.wav')
        path = os.path.join(sublime.packages_path(), 'KSP (Kontakt Script Processor)', 'sounds')
        filepath = os.path.join(path, 'finished.wav')

        if not os.path.exists(path):
            os.makedirs(path)

            # but only copy it if it doesn't exist already, so users can override it if need be
            if not os.path.exists(filepath):
                with open(filepath, 'wb') as sound:
                    sound.write(res)
    except:
        pass

    settings = sublime.load_settings('KSP.sublime-settings')
    enable_vanilla_builtins = bool(settings.get('ksp_add_completions_for_vanilla_builtins', False))

    if sublime_version >= 4000:
        builtin_compl_vars.extend(sublime.CompletionItem(trigger = x[1:],
                                                         annotation = 'variable',
                                                         completion = x[1:],
                                                         kind = sublime.KIND_VARIABLE) for x in all_builtins)

        if enable_vanilla_builtins:
            builtin_compl_vars.extend(sublime.CompletionItem(trigger = x,
                                                             annotation = 'variable',
                                                             completion = x,
                                                             kind = sublime.KIND_VARIABLE) for x in all_builtins)
    else:
        builtin_compl_vars.extend(('%s\tvariable' % x[1:], x[1:]) for x in all_builtins)

        if enable_vanilla_builtins:
            # $ needs to be prepended by \ else executing completion will remove it as if it were a snippet variable
            builtin_compl_vars.extend(('%s\tvariable' % x, '\\' + x if x[0] == '$' else x) for x in all_builtins)

        builtin_compl_vars.sort()

    for f in functions:
        for s in function_signatures[f]:
            args = [a.replace('-', '_') for a in s[0]]
            snippet_args = ['${%d:%s}' % (i + 1, a) for i, a in enumerate(args)]

            if snippet_args:
                args_str = '(%s)' % ', '.join(snippet_args)
                formatted_args = str(args).replace('\'', '').strip('[]')
            elif f in functions_with_forced_parentheses:
                args_str = '()'
                formatted_args = args_str
            else:
                args_str = ''
                formatted_args = args_str

            if args_str != formatted_args:
                formatted_args = '(' + formatted_args + ')' if formatted_args else ''

            if sublime_version >= 4000:
                function_details = '<b>Returns</b>: %s' % (s[1])

                builtin_compl_funcs.append(sublime.CompletionItem(trigger = f + formatted_args,
                                                                  annotation = 'function',
                                                                  completion = f + args_str,
                                                                  details = function_details,
                                                                  completion_format = sublime.COMPLETION_FORMAT_SNIPPET,
                                                                  kind = sublime.KIND_FUNCTION))
            else:
                completion = ['%s%s\tfunction' % (f, formatted_args), '%s%s' % (f, args_str)]

                builtin_compl_funcs.append(tuple(completion))
                builtin_compl_funcs.sort()

    # control par references that can be used as control -> x, or control -> value
    remap_control_pars = {'POS_X': 'x', 'POS_Y': 'y', 'MAX_VALUE': 'MAX', 'MIN_VALUE': 'MIN', 'DEFAULT_VALUE': 'DEFAULT'}

    for x in builtins:
        completion = []
        name = None
        original_variable = x

        if x.startswith('$CONTROL_PAR_'):
            x = x.replace('$CONTROL_PAR_', '')
            x = remap_control_pars.get(x, x).lower()
            completion.append(('%s\tui param' % x, x))
            name = 'ui param'

        if re.search(r'^\$EVENT_PAR_[0-3]', x):
            x = x.replace('$EVENT_', '').lower()
            completion.append(('%s\tevent param' % x, x))
            name = 'event param'
        elif x.startswith('$EVENT_PAR_'):
            x = x.replace('$EVENT_PAR_', '').lower()
            completion.append(('%s\tevent param' % x, x))
            name = 'event param'

        if completion:
            if sublime_version >= 4000:
                magic_control_and_event_pars.append(sublime.CompletionItem(trigger = x,
                                                                           annotation = name,
                                                                           completion = x,
                                                                           details = original_variable ,
                                                                           completion_format = sublime.COMPLETION_FORMAT_SNIPPET,
                                                                           kind = sublime.KIND_VARIABLE))
            else:
                magic_control_and_event_pars.append(tuple(completion[0]))
                magic_control_and_event_pars.sort()

    if sublime_version >= 4000:
        from sublime_lib import ResourcePath

        snippets_path = ResourcePath('Packages', __package__, 'snippets')
        snippet_list = snippets_path.children()

        for s in snippet_list:
            snippet     = s.read_text()
            tree        = ET.fromstring(snippet)
            name        = tree.findtext('description')
            tabTrigger  = tree.findtext('tabTrigger')
            content     = tree.findtext('content').replace('\n', '', 1)

            builtin_snippets.append(sublime.CompletionItem.snippet_completion(trigger = tabTrigger,
                                                                              snippet = content,
                                                                              annotation = name))

class KspCompletions(sublime_plugin.EventListener):
    '''Handles KSP autocompletions'''

    def _extract_completions(self, view, prefix, point):
        # the sublime view.extract_completions implementation doesn't seem to allow for
        # the . character to be included in the prefix irrespectively of the "word_separators" setting

        if '.' in prefix:
            # potentially slow work around for the case where there is a period in the prefix
            code = view.substr(sublime.Region(0, view.size()))
            return sorted(re.findall(re.escape(prefix) + r'[a-zA-Z0-9_.]+', code))
        else:
            return view.extract_completions(prefix, point) # default implementation if no '.' in the prefix

    def unique(self, seq):
        seen = set()

        for item in seq:
            if item not in seen:
                seen.add(item)
                yield item

    def on_query_completions(self, view, prefix, locations):
        # parts of the code inspired by: https://github.com/agibsonsw/AndyPython/blob/master/PythonCompletions.py

        global builtin_compl_vars, builtin_compl_funcs, magic_control_and_event_pars, builtin_snippets

        if not view.match_selector(locations[0], 'source.ksp -string -comment -constant'):
            return []

        pt = locations[0] # - len(prefix) - 1
        line_start_pos = view.line(sublime.Region(pt, pt)).begin()
        line = view.substr(sublime.Region(line_start_pos, pt))    # the character before the trigger

        compl = self._extract_completions(view, prefix, pt)

        if re.match(r' *declare .*', line) and ':=' not in line:
            compl = []
        elif re.match(r'.*-> ?[a-zA-Z_]*$', line): # if the line ends with something like '->' or '-> value'
            compl.clear
            compl = magic_control_and_event_pars
        else:
            compl = self._extract_completions(view, prefix, pt)
            compl = [(item + "\tdefault", item.replace('$', '\\$', 1))
                     for item in compl
                         if len(item) > 3 and item not in builtins
                    ]

            if '.' not in prefix:
                bc = []
                bc.extend(builtin_compl_vars)
                bc.extend(builtin_compl_funcs)
                compl.extend(bc)

            if sublime_version >= 4000:
                compl.extend(builtin_snippets)

        if sublime_version >= 4000:
            sublime.CompletionList(compl, sublime.INHIBIT_WORD_COMPLETIONS | sublime.INHIBIT_EXPLICIT_COMPLETIONS)
        else:
            compl = self.unique(compl)

        return (compl, sublime.INHIBIT_WORD_COMPLETIONS | sublime.INHIBIT_EXPLICIT_COMPLETIONS)


class NumericSequenceCommand(sublime_plugin.TextCommand):
    '''Tool for incrementing selected text'''

    def run(self, edit):
        if len(self.view.sel()) < 2:
            return

        start = self.view.substr(self.view.sel()[0])

        if start and not re.match(r'\d+', start):
            return

        start = int(start) if start else 1

        for i, selection in enumerate(self.view.sel()):
            self.view.replace(edit, selection, str(start + i))

class OpenPathFromImportOrPragmaCommand(sublime_plugin.TextCommand):
    '''Tries to recognize the path used in import or save_compiled_source pragma statements
       and opens it in a new Sublime Text view'''

    def run(self, edit):
        v = self.view

        for region in v.sel():
            line = v.substr(v.line(region))

            for m in pragma_and_import_re.finditer(line):
                for g in m.groups():
                    if g != None:
                        path = g.strip()

                if not os.path.isabs(path):
                    if v.file_name() == None:
                        return

                    parent = os.path.dirname(v.file_name())
                    path = os.path.realpath(os.path.join(parent, path))

                if not os.path.exists(path):
                    return
                else:
                    if os.path.isfile(path):
                        sublime.active_window().open_file(path)
                    elif os.path.isdir(path):
                        paths = []

                        for f in os.listdir(path):
                            split = os.path.splitext(f)

                            if split[1] == '.ksp':
                                paths.append(os.path.join(path, f))

                        if paths:
                            sublime.run_command('new_window')

                            for f in paths:
                                sublime.active_window().open_file(os.path.join(path, f))
                        else:
                            sublime.active_window().run_command('open_dir', {'dir': path})


class ReplaceTextWithCommand(sublime_plugin.TextCommand):
    def run(self, edit, new_text = ''):
        self.view.replace(edit, sublime.Region(0, self.view.size()), new_text)


class KspGlobalSettingToggleCommand(sublime_plugin.ApplicationCommand):
    '''Handles toggeled sublime settings'''

    def run(self, setting, default):
        sksp_options_dict = {
            'ksp_compact_output'                       : 'Remove Indents and Empty Lines',
            'ksp_compact_variables'                    : 'Compact Variables',
            'ksp_extra_checks'                         : 'Extra Syntax Checks',
            'ksp_optimize_code'                        : 'Optimize Compiled Code',
            'ksp_combine_callbacks'                    : 'Combine Duplicate Callbacks',
            'ksp_add_compiled_date'                    : 'Add Compilation Date/Time Comment',
            'ksp_sanitize_exit_command'                : 'Sanitize Behavior of \'exit\' Command',
            'ksp_comment_inline_functions'             : 'Insert Comments When Expanding Functions',
            'ksp_play_sound'                           : 'Play Sound When Compilation Finishes',
            'ksp_add_completions_for_vanilla_builtins' : 'Enable Completions for Vanilla KSP Built-ins',
        }

        settings = sublime.load_settings('KSP.sublime-settings')
        settings.set(setting, not settings.get(setting, default))
        sublime.save_settings('KSP.sublime-settings')

        if settings.get(setting, default):
            option_toggle = 'enabled!'
        else:
            option_toggle = 'disabled!'

        utils.log_message('SublimeKSP option %s is %s' % (sksp_options_dict[setting], option_toggle))

    def is_checked(self, setting, default):
        return bool(sublime.load_settings('KSP.sublime-settings').get(setting, default))

    def is_enabled(self, setting, default):
        settings = sublime.load_settings('KSP.sublime-settings')
        extra_checks = bool(settings.get('ksp_extra_checks', True))

        if setting == 'ksp_optimize_code':
            return extra_checks
        else:
            return True


class KspIndentListener(sublime_plugin.EventListener):
    def on_text_command(self, view, command_name, args):
        if command_name == 'reindent' and view.sel()[0].size() > 0:
            return ('ksp_reindent', args)
        else:
            return None


class KspReindent(sublime_plugin.TextCommand):
    def get_indent(self, line):
        return line[:len(line) - len(line.lstrip())]

    def reindent(self, lines, indent):
        increase_indent = re.compile(r'\s*(on|const|if|else|select|while|function|taskfunc|macro|for|family|struct|list|property|case)\b')
        decrease_indent = re.compile(r'(?m)^\s*(end\s+(\w+)|case\b|else\b)')

        result = []
        last_line = None

        for line in lines:
            if last_line is not None:
                m = increase_indent.match(last_line)
                ind = self.get_indent(last_line)

                if m:
                    if m.group(1) == 'select':
                        ind = ind + indent * 2
                    else:
                        ind = ind + indent

                m = decrease_indent.match(line)

                if m:
                    if line.lstrip().startswith('end select'):
                        ind = ind.replace(indent, '', 2)
                    else:
                        ind = ind.replace(indent, '', 1)

                line = ind + line.lstrip()

            if line.strip():
                last_line = line

            result.append(line)

        return result

    def run(self, edit, **kwargs):
        tab_size = int(self.view.settings().get('tab_size', 8))
        use_spaces = self.view.settings().get('translate_tabs_to_spaces', True)
        indent = ' ' * tab_size if use_spaces else '\t'

        for sel in self.view.sel():
            code = self.view.substr(sel)
            code = '\n'.join(self.reindent(code.split('\n'), indent))
            self.view.replace(edit, sel, code)


class KspOnEnter(sublime_plugin.TextCommand):
    def get_line(self, lineno):
        if not (0 <= lineno <= self.get_last_lineno()):
            return ''

        return self.view.substr(self.view.line(self.view.text_point(lineno, 0)))

    def get_last_lineno(self):
        row, col = self.view.rowcol(self.view.size())
        return row

    def get_indent(self, line):
        return re.match(r'(\s*)', line).group(1)

    def run(self, edit):
        self.view.run_command('insert', {'characters': '\n'})

        for selection in self.view.sel():
            row, col = self.view.rowcol(selection.begin())
            prev_line = self.get_line(row - 1)
            this_line = self.get_line(row)
            next_line = self.get_line(row + 1)

            m = re.match(r'\s*(list|const|struct|on|if|select|while|function|taskfunc|macro|for|family|property)\b', prev_line)

            # if the next line is not an 'end ...' line, the next line is not already more indented and the regexp matched
            if (not (next_line and next_line.lstrip().startswith('end ') and
                len(self.get_indent(next_line)) == len(self.get_indent(prev_line))) and
                len(self.get_indent(next_line)) <= len(self.get_indent(prev_line)) and m):

                # insert end text
                indent = self.get_indent(prev_line)
                end_line = '\n%send %s' % (indent, m.group(1))
                self.view.insert(edit, selection.b, end_line)

                # remove the old selection and add a new
                self.view.sel().subtract(self.view.line(self.view.text_point(row+1, 0)))
                self.view.sel().add(sublime.Region(self.view.text_point(row, len(this_line))))

            self.view.run_command('move_to', {"to": "eol"})


class KspUncompressCode(sublime_plugin.TextCommand):
    def run(self, edit):
        global last_compiler

        if last_compiler:
            uncompress = last_compiler.uncompress_variable_names
            selections = self.view.sel()

            if len(selections) == 1 and selections[0].empty():
                selections = [sublime.Region(0, self.view.size())]

            for selection in selections:
                code = self.view.substr(selection)
                self.view.replace(edit, selection, uncompress(code))

    def is_enabled(self):
        # only show the command when a file with KSP syntax highlighting is visible
        return 'KSP.sublime-syntax' in self.view.settings().get('syntax', '')

class KspAboutCommand(sublime_plugin.ApplicationCommand):
    def run(self):
        webbrowser.open('https://github.com/nojanath/SublimeKSP/wiki')


class KspFixLineEndingsAndSetSyntax(sublime_plugin.EventListener):
    def is_probably_ksp_file(self, view):
        fn = view.file_name()
        ext = ''

        if fn:
            ext = os.path.splitext(fn)[1].lower()

        if ext == '.ksp' or ext == '.b3s' or ext == '.nbsc':
            return True
        elif ext == '.txt' or ext == '':
            code = view.substr(sublime.Region(0, 5000))
            score = sum(sc for (pat, sc) in [(r'on\s*init\b', 1),
                                             (r'on\s*note\b', 1),
                                             (r'on\s*release\b', 1),
                                             (r'on\s*controller\b', 1),
                                             (r'on\s*listener', 2),
                                             (r'on\s*persistence', 2),
                                             (r'on\s*ui_control', 3),
                                             (r'end\s*function', 1),
                                             (r'end\s*macro', 1),
                                             (r'end\s*on', 1),
                                             (r'EVENT_ID', 2),
                                             (r'EVENT_NOTE', 2),
                                             (r'EVENT_VELOCITY', 2),
                                             (r'declare\s*\w+\[\w+\]', 2),
                                             (r'define\s*', 2),
                                             (r'import\s*[\"\']', 1),
                                             (r'instpers', 2),
                                             (r'make_perfview', 3),
                                             (r'make_persistent', 2),
                                             (r'make_instr', 2),
                                             (r'message\s*\(', 1)]
                            if re.search('(?m)' + pat, code)
                        )
            return score >= 2
        else:
            return False

    def set_ksp_syntax(self, view):
        view.set_syntax_file("KSP.sublime-syntax")

    def test_and_set_syntax_to_ksp(self, view):
        is_ksp_syntax = False

        if view.settings().get('syntax') == "KSP.sublime-syntax":
            is_ksp_syntax = True

        if self.is_probably_ksp_file(view):
            fn = view.file_name()

            if fn and not is_ksp_syntax:
                with io.open(view.file_name(), 'r', encoding = 'latin-1') as file:
                    s = file.read()

                    mixed_line_endings = re.search(r'\r(?!\n)', s) and '\r\n' in s

                    if mixed_line_endings:
                        s, changes = re.subn(r'\r+\n', '\n', s) # normalize line endings

                        if changes:
                            # strip trailing whitespace too while we're at it
                            s = '\n'.join(x.rstrip() for x in s.split('\n'))

                            view.run_command('replace_text_with', {'new_text': s})
                            sublime.set_timeout(lambda: utils.log_message('EOL characters automatically fixed! Please save to keep the changes.'), 100)

            self.set_ksp_syntax(view)

    def on_load_async(self, view):
        self.test_and_set_syntax_to_ksp(view)

    def on_reload_async(self, view):
        self.test_and_set_syntax_to_ksp(view)

    def on_post_save_async(self, view):
        self.test_and_set_syntax_to_ksp(view)

    def on_clone_async(self, view):
        self.test_and_set_syntax_to_ksp(view)

    def on_modified_async(self, view):
        self.test_and_set_syntax_to_ksp(view)

    def on_activated_async(self, view):
        self.test_and_set_syntax_to_ksp(view)
