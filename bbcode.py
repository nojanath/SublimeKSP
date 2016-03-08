import sublime_plugin
import sublime
import os.path
from plistlib import readPlistFromBytes
import itertools

def get_ranges(iter):
    ' given "AABBBA" returns ranges where the value does not change, eg. [(0,2,"A"), (2,5,"B"), (5,1,"A")] '
    last_value = None
    start = 0
    iter = itertools.chain(iter, itertools.repeat(None, 1)) # add a None at the end of the iterator
    for i, v in enumerate(iter):
        if v != last_value:
            if last_value is not None:
                yield (start, i, last_value)
            start = i
        last_value = v

class CopyAsBbCode(sublime_plugin.ApplicationCommand):

    def __init__(self):
        sublime_plugin.ApplicationCommand.__init__(self)

    def is_visible(self):
        # only show the command when a file with KSP syntax highlighting is visible
        view = sublime.active_window().active_view()
        return 'KSP.tmLanguage' in view.settings().get('syntax', '')

    def apply_style(self, scopes, plist, text):
        style = {}
        for scope in scopes.split():
            [style.update(st['settings']) for st in plist['settings'][1:] if scope.startswith(st['scope'])]
        start, end = [], []
        if 'foreground' in style and style['foreground'].strip().startswith('#'):
            fg = style['foreground']
            if len(fg) == 4:
                fg = '#' + fg[1]*2 + fg[2]*2 + fg[3]*2
            start.insert(0, '[color=%s]' % fg)
            end.append('[/color]')
        if 'fontStyle' in style and 'italic' in style['fontStyle']:
            start.insert(0, '[i]')
            end.append('[/i]')
        if 'fontStyle' in style and 'bold' in style['fontStyle']:
            start.insert(0, '[b]')
            end.append('[/b]')
        return ''.join(start) + text + ''.join(end)

    def run(self, *args, **kwargs):
        view = sublime.active_window().active_view()

        #settings = sublime.load_settings('KSP.sublime-settings')
        #scheme_file = settings.get('color_scheme', 'Packages/SublimeKSP/KScript Light.tmTheme')
        scheme_file = 'Packages/SublimeKSP/KScript Light.tmTheme'
        plist = readPlistFromBytes(sublime.load_binary_resource(scheme_file))

        result = ['[pre]']
        start, end = view.sel()[0].a, view.sel()[0].b
        if start == end:
            start, end = 0, view.size()
        for a, b, scopes in get_ranges(view.scope_name(i) for i in range(start, end)):
            result.append(self.apply_style(scopes, plist, view.substr(sublime.Region(start+a, start+b))))
        result.append('[/pre]')
        sublime.set_clipboard(''.join(result))
