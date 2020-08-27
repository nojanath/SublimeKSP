import sublime
import sublime_plugin

import codecs
import traceback
import os.path
import sys
import re
import threading
import webbrowser

sys.path.append(os.path.dirname(__file__))
sys.path.append(os.path.join(os.path.dirname(__file__), 'ksp_compiler3'))

import ksp_compiler
import ksp_ast

import urllib, tarfile, json, shutil
from subprocess import call
try:
    import winsound
except Exception:
    pass

last_compiler = None

class KspRecompile(sublime_plugin.ApplicationCommand):
    def is_enabled(self):
        # only show the command when a file with KSP syntax highlighting is visible
        view = sublime.active_window().active_view()
        if view:
            return 'KSP.sublime-syntax' in view.settings().get('syntax', '')

    def run(self, *args):
        sublime.active_window().run_command('compile_ksp', {'recompile': True})

class CompileKspCommand(sublime_plugin.ApplicationCommand):
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
        # wait until any previous thread is finished
        if self.thread and self.thread.is_alive():
            sublime.status_message('Waiting for earlier compilation to finish...')
            self.thread.stop()
            self.thread.join()

        # find the view containing the code to compile
        view = None
        if kwargs.get('recompile', None) and self.last_filename:
            view = CompileKspThread.find_view_by_filename(self.last_filename)
        if view is None:
            view = sublime.active_window().active_view()

        self.thread = CompileKspThread(view)
        self.thread.start()
        self.last_filename = view.file_name()

class CompilerSounds:
    dir = None

    def __init__(self):
        self.dir = os.path.join(os.path.dirname(__file__), 'sounds')

    def play(self, **kwargs):
        sound_path = os.path.join(self.dir, '{}.wav'.format(kwargs['command']))

        if sublime.platform() == "osx":
            if os.path.isfile(sound_path):
                call(["afplay", "-v", str(1), sound_path])

        if sublime.platform() == "windows":
            if os.path.isfile(sound_path):
                winsound.PlaySound(sound_path, winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)

        if sublime.platform() == "linux":
            if os.path.isfile(sound_path):
                call(["aplay", sound_path])

class CompileKspThread(threading.Thread):
    def __init__(self, view):
        threading.Thread.__init__(self)
        self.base_path = None
        self.compiler = None
        self.view = view

    def stop(self):
        if self.compiler:
            self.compiler.abort_compilation()

    def compile_on_progress(self, text, percent_complete):
        sublime.status_message('Compiling (%d%%) - %s...' %
                              (percent_complete, text))

    @classmethod
    def find_view_by_filename(cls, filename, base_path=None):
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
        sublime.status_message('Error - compilation aborted!')
        sublime.error_message(error_msg)
        sublime.status_message('')

    def read_file_function(self, filepath):
        if filepath.startswith('http://'):
            from urllib.request import urlopen
            s = urlopen(filepath, timeout=5).read().decode('utf-8')
            return re.sub('\r+\n*', '\n', s)

        if self.base_path:
            filepath = os.path.join(self.base_path, filepath)
        filepath = os.path.abspath(filepath)
        view = CompileKspThread.find_view_by_filename(filepath, self.base_path)
        if view is None:
            s = codecs.open(filepath, 'r', 'utf-8').read()
            return re.sub('\r+\n*', '\n', s)
        else:
            return view.substr(sublime.Region(0, view.size()))

    def run(self, *args):
        global last_compiler

        view = self.view
        code = view.substr(sublime.Region(0, view.size()))
        filepath = view.file_name()
        if filepath:
            self.base_path = os.path.dirname(filepath)
        else:
            self.base_path = None

        settings = sublime.load_settings("KSP.sublime-settings")

        compact = settings.get('ksp_compact_output', False)
        compactVars = settings.get('ksp_compact_variables', False)
        check = settings.get('ksp_extra_checks', True)
        optimize = settings.get('ksp_optimize_code', False)
        comments_on_expansion = settings.get('ksp_comment_inline_functions', False)
        check_empty_compound_statements = settings.get('ksp_signal_empty_ifcase', True)
        add_compiled_date_comment = settings.get('ksp_add_compiled_date', True)
        should_play_sound = settings.get('ksp_play_sound', False)

        error_msg = None
        error_lineno = None
        error_filename = filepath # path to main script

        sound_utility = CompilerSounds()

        try:
            sublime.status_message('Compiling...')

            self.compiler = ksp_compiler.KSPCompiler(code, self.base_path, compact, compactVars, comments_on_expansion,
                                                     read_file_func=self.read_file_function,
                                                     extra_syntax_checks=check,
                                                     optimize=optimize and check,
                                                     check_empty_compound_statements=check_empty_compound_statements,
                                                     add_compiled_date_comment=add_compiled_date_comment)
            if self.compiler.compile(callback=self.compile_on_progress):
                last_compiler = self.compiler
                code = self.compiler.compiled_code
                code = code.replace('\r', '')
                if self.compiler.output_file:
                    if not os.path.isabs(self.compiler.output_file):
                        self.compiler.output_file = os.path.join(self.base_path, self.compiler.output_file)
                    codecs.open(self.compiler.output_file, 'w', 'latin-1').write(code)
                    sublime.status_message("Successfully compiled (compiled code saved to %s)." % self.compiler.output_file)
                else:
                    sublime.status_message("Successfully compiled (the code is now on the clipboard ready to be pasted into Kontakt).")
                    sublime.set_clipboard(code)
            else:
                sublime.status_message('Compilation aborted.')
        except ksp_ast.ParseException as e:
            error_msg = unicode(e)
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
            if should_play_sound:
                sound_utility.play(command="error")
        else:
            if should_play_sound:
                sound_utility.play(command="finished")

    def description(self, *args):
        return 'Compiled KSP'

# **********************************************************************************************

from ksp_compiler3.ksp_builtins import keywords, variables, functions, function_signatures
all_builtins = set(functions.keys()) | set([v[1:] for v in variables]) | variables | keywords
functions, variables = set(functions), set(variables)

builtin_compl_vars = []
builtin_compl_vars.extend(('%s\tvariable' % v[1:], v[1:]) for v in variables)
builtin_compl_vars.sort()

builtin_compl_funcs = []
for f in functions:
    args = [a.replace('number variable or text','').replace('-', '_') for a in function_signatures[f][0]]
    args = ['${%d:%s}' % (i+1, a) for i, a in enumerate(args)]
    args_str = '(%s)' % ', '.join(args) if args else ''
    builtin_compl_funcs.append(("%s\tfunction" % (f), "%s%s" % (f,args_str)))
builtin_compl_funcs.sort()

# control par references that can be used as control->x, or control->value
magic_control_pars = []
remap_control_pars = {'POS_X': 'x', 'POS_Y': 'y', 'MAX_VALUE': 'MAX', 'MIN_VALUE': 'MIN', 'DEFAULT_VALUE': 'DEFAULT'}
for v in variables:
    if v.startswith('$CONTROL_PAR_'):
        v = v.replace('$CONTROL_PAR_', '')
        v = remap_control_pars.get(v, v).lower()
        magic_control_pars.append(('%s\tui param' % v, v))
magic_control_pars.sort()


class KSPCompletions(sublime_plugin.EventListener):
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
        global builtin_compl_vars, builtin_compl_funcs, magic_control_pars
        if not view.match_selector(locations[0], 'source.ksp -string -comment -constant'):
            return []
        pt = locations[0] # - len(prefix) - 1
        line_start_pos = view.line(sublime.Region(pt, pt)).begin()
        line = view.substr(sublime.Region(line_start_pos, pt))    # the character before the trigger

        if re.match(r' *declare .*', line) and ':=' not in line:
            compl = []
        elif re.match(r'.*-> ?[a-zA-Z_]*$', line): # if the line ends with something like '->' or '->valu'
            compl = magic_control_pars
        else:
            compl = self._extract_completions(view, prefix, pt)
            compl = [(item + "\tdefault", item.replace('$', '\\$', 1)) for item in compl
                     if len(item) > 3 and item not in all_builtins]
            if '.' not in prefix:
                bc = []
                bc.extend(builtin_compl_vars)
                bc.extend(builtin_compl_funcs)
                compl.extend(bc)
        compl = self.unique(compl)

        return (compl, sublime.INHIBIT_WORD_COMPLETIONS |
                sublime.INHIBIT_EXPLICIT_COMPLETIONS)


class NumericSequenceCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        if len(self.view.sel()) < 2:
            return
        start = self.view.substr(self.view.sel()[0])
        if start and not re.match(r'\d+', start):
            return
        start = int(start) if start else 1

        for i, selection in enumerate(self.view.sel()):
            self.view.replace(edit, selection, str(start + i))


class ReplaceTextWithCommand(sublime_plugin.TextCommand):
    def run(self, edit, new_text=''):
        self.view.replace(edit, sublime.Region(0,self.view.size()),new_text)


class KspGlobalSettingToggleCommand(sublime_plugin.ApplicationCommand):
    def run(self, setting, default):
        sksp_options_dict = {
            "ksp_compact_output" : "Remove Indents and Empty Lines",
            "ksp_compact_variables" : "Compact Variables",
            "ksp_extra_checks" : "Extra Syntax Checks",
            "ksp_optimize_code" : "Optimize Compiled Code",
            "ksp_signal_empty_ifcase" : "Raise Error on Empty 'if' or 'case' Statements",
            "ksp_add_compiled_date" : "Add Compilation Date/Time Comment",
            "ksp_comment_inline_functions" : "Insert Comments When Expanding Functions",
            "ksp_play_sound" : "Play Sound When Compilation Finishes"
        }

        s = sublime.load_settings("KSP.sublime-settings")
        s.set(setting, not s.get(setting, False))
        sublime.save_settings("KSP.sublime-settings")

        if s.get(setting, False):
            option_toggle = "enabled!"
        else:
            option_toggle = "disabled!"

        sublime.status_message('SublimeKSP option %s is %s' % (sksp_options_dict[setting], option_toggle))

    def is_checked(self, setting, default):
        return bool(sublime.load_settings("KSP.sublime-settings").get(setting, default))

    def is_enabled(self, setting, default):
        extra_checks = bool(sublime.load_settings("KSP.sublime-settings").get("ksp_extra_checks", default))
        optim_code = bool(sublime.load_settings("KSP.sublime-settings").get("ksp_optimize_code", default))
        signal_empty = not (extra_checks and optim_code)

        if setting == "ksp_optimize_code":
            return extra_checks
        elif setting == "ksp_signal_empty_ifcase":
            return signal_empty
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
        increase_indent = re.compile(r'\s*(on|if|else|select|while|function|taskfunc|macro|for|family|property|case)\b')
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
            prev_line = self.get_line(row-1)
            this_line = self.get_line(row)
            next_line = self.get_line(row+1)
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


class KspFixLineEndings(sublime_plugin.EventListener):
    def is_probably_ksp_file(self, view):
        ext = os.path.splitext(view.file_name())[1].lower()
        if ext == '.ksp' or ext == '.b3s' or ext == '.nbsc':
            return True
        elif ext == '.txt':
            code = view.substr(sublime.Region(0, view.size()))
            score = sum(sc for (pat, sc) in [(r'^on init\b', 1), (r'^on note\b', 1), (r'^on release\b', 1), (r'^on controller\b', 1), ('^end function', 1), ('EVENT_ID', 2), ('EVENT_NOTE', 2), ('EVENT_VELOCITY', 2), ('^on ui_control', 3), (r'make_persistent', 2), ('^end on', 1), (r'-> result', 2), (r'declare \w+\[\w+\]', 2)]
                        if re.search('(?m)' + pat, code))
            return score >= 2
        else:
            return False

    def set_ksp_syntax(self, view):
        view.set_syntax_file("KSP.sublime-syntax")

    def on_load(self, view):
        if self.is_probably_ksp_file(view):
            s = codecs.open(view.file_name(), 'r', 'latin-1').read()
            mixed_line_endings = re.search(r'\r(?!\n)', s) and '\r\n' in s
            if mixed_line_endings:
                s, changes = re.subn(r'\r+\n', '\n', s) # normalize line endings
                if changes:
                    s = '\n'.join(x.rstrip() for x in s.split('\n')) # strip trailing white-space too while we're at it
                    view.run_command('replace_text_with', {'new_text': s})
                    sublime.set_timeout(lambda: sublime.status_message('EOL characters automatically fixed. Please save to keep the changes.'), 100)
            self.set_ksp_syntax(view)
