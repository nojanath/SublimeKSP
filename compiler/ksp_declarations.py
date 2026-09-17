# ksp-compiler - a compiler for the Kontakt script language
# Copyright (C) 2011  Nils Liberg
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version:
# http://www.gnu.org/licenses/gpl-2.0.html
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

'''Finds function, taskfunc and macro declarations in a script and the files it imports,
   so that the editor can offer them as snippet completions'''

import collections
import io
import os
import re

from ksp_compiler import comment_or_string_re, line_continuation_re

Declaration = collections.namedtuple('Declaration', 'kind name params has_parens returns filename')

function_re = re.compile(r'''
    ^[ \t]*
    (?P<kind>function|taskfunc)
    [ \t]+
    (?P<name>[a-zA-Z_][\w.]*)
    (?![\w.#])                                      # templated names like foo_#x# can't be called as they are
    [ \t]*
    (?P<parens>\((?P<params>[^()\n]*)\))?
    (?:[ \t]*->[ \t]*(?P<returns>[a-zA-Z_]\w*))?
''', re.MULTILINE | re.VERBOSE)

macro_re = re.compile(r'''
    ^[ \t]*
    (?P<kind>macro)
    [ \t]+
    (?P<name>[a-zA-Z0-9_]+(?:\.[a-zA-Z0-9_]+)*)
    (?![\w.#])
    [ \t]*
    (?P<parens>\((?P<params>[^()\n]*)\))?
''', re.MULTILINE | re.VERBOSE)

import_re = re.compile(r'''
    ^[ \t]*
    import[ \t]+
    (?P<quote>["'])(?P<filename>.+?)(?P=quote)
    (?:[ \t]+as[ \t]+(?P<asname>[a-zA-Z_][\w.]*))?
''', re.MULTILINE | re.VERBOSE)

ignore_re = re.compile(r'^[ \t]*__IGNORE__', re.MULTILINE)

def strip_comments(source):
    '''Removes comments (keeping line breaks, strings and everything else) and joins continued lines'''
    def replace(m):
        if m.group('comment'):
            return '\n' * m.group('comment').count('\n')

        return m.group(0)

    source = source.replace('\r\n', '\n').replace('\r', '\n')
    source = comment_or_string_re.sub(replace, source)

    return line_continuation_re.sub('', source)

def split_params(params):
    return [p.strip() for p in params.split(',') if p.strip()]

def parse_source(source, filename = None):
    '''Returns a tuple of (declarations, imports) found in the source code.
       Imports are (path, asname) tuples, and paths are as written in the import statement'''
    source = strip_comments(source)

    if ignore_re.search(source):
        return ([], [])

    declarations = []

    for m in function_re.finditer(source):
        params = split_params(m.group('params') or '')

        # taskfunc parameters can be preceded by a var or out modifier
        if m.group('kind') == 'taskfunc':
            params = [p.split()[-1] for p in params]

        declarations.append((m.start(), Declaration(m.group('kind'), m.group('name'), params,
                                                    bool(m.group('parens')), m.group('returns'), filename)))

    for m in macro_re.finditer(source):
        params = split_params(m.group('params') or '')
        declarations.append((m.start(), Declaration('macro', m.group('name'), params,
                                                    bool(m.group('parens')), None, filename)))

    declarations = [d for _, d in sorted(declarations, key = lambda x: x[0])]
    imports = [(m.group('filename'), m.group('asname')) for m in import_re.finditer(source)]

    return (declarations, imports)

def real_file_path(path):
    '''Normalized path with symlinks resolved, so a file reached through different links compares equal'''
    return os.path.normcase(os.path.realpath(path))

def snippet_escape(s):
    return s.replace('\\', '\\\\').replace('$', '\\$').replace('}', '\\}')

def trigger(declaration):
    '''Text shown in the completion list, e.g. my_function(x, y)'''
    if declaration.params or declaration.has_parens:
        return '%s(%s)' % (declaration.name, ', '.join(declaration.params))

    return declaration.name

def snippet(declaration):
    '''Snippet inserted by the completion, e.g. my_function(${1:x}, ${2:y})'''
    name = snippet_escape(declaration.name)

    if declaration.params or declaration.has_parens:
        args = ['${%d:%s}' % (i + 1, snippet_escape(p)) for i, p in enumerate(declaration.params)]
        return '%s(%s)' % (name, ', '.join(args))

    return name

class DeclarationScanner:
    '''Collects declarations from a source string and, recursively, from the files it imports.
       Imported files are only re-read when their modification time or size changes'''

    def __init__(self):
        self.file_cache = {}  # path -> ((mtime, size), (declarations, imports))

    def parse_file(self, path):
        try:
            stat = os.stat(path)
        except OSError:
            return None

        key = (stat.st_mtime, stat.st_size)
        cached = self.file_cache.get(path)

        if cached and cached[0] == key:
            return cached[1]

        try:
            with io.open(path, 'r', encoding = 'utf-8', errors = 'replace') as f:
                parsed = parse_source(f.read(), os.path.basename(path))
        except OSError:
            return None

        self.file_cache[path] = (key, parsed)

        return parsed

    def resolve_relative_import(self, basepath, filename):
        '''The compiler resolves imports relative to the folder of the script being compiled. A library file that is
           open on its own is usually imported by a script elsewhere, so its import paths might not exist relative
           to its own folder. In that case, try the parent folders, then drop leading folders from the import path'''
        basepath = os.path.abspath(basepath)
        candidates = []
        folder = basepath

        while True:
            candidates.append(os.path.join(folder, filename))
            parent = os.path.dirname(folder)

            if parent == folder:
                break

            folder = parent

        parts = [p for p in re.split(r'[\\/]', filename) if p not in ('', '.', '..')]

        for i in range(1, len(parts)):
            candidates.append(os.path.join(basepath, *parts[i:]))

        for candidate in candidates:
            if os.path.exists(candidate):
                return os.path.abspath(candidate)

        return None

    def import_paths(self, basepath, filename, guess_paths = True):
        # remote imports would need a network request on every completion
        if filename.startswith('http://') or filename.startswith('https://'):
            return []

        if os.path.isabs(filename):
            path = os.path.abspath(filename)
        elif basepath and guess_paths:
            path = self.resolve_relative_import(basepath, filename)
        elif basepath:
            path = os.path.abspath(os.path.join(basepath, filename))
        else:
            return []

        if not path:
            return []

        if os.path.isdir(path):
            paths = []

            for root, dirs, files in os.walk(path):
                dirs.sort()
                paths.extend(os.path.join(root, f) for f in sorted(files) if os.path.splitext(f)[1] == '.ksp')

            return paths
        elif os.path.isfile(path):
            return [path]

        return []

    def walk(self, parsed, basepath, filepath = None, guess_paths = True):
        '''Walks parsed source code and the files it imports. Returns a tuple of (declarations with names prefixed
           by import namespaces, set of real paths of the imported files). Like the compiler, import paths are
           resolved relative to basepath, and guess_paths enables the fallbacks in resolve_relative_import'''
        declarations = []
        visited = set()
        imported_files = set()

        def collect(parsed, namespaces, import_chain):
            decls, imports = parsed

            for d in decls:
                declarations.append(d._replace(name = '.'.join(namespaces + (d.name,))))

            for import_filename, asname in imports:
                import_namespaces = namespaces + tuple(asname.split('.')) if asname else namespaces

                for path in self.import_paths(basepath, import_filename, guess_paths):
                    real_path = real_file_path(path)
                    key = (real_path, import_namespaces)

                    if key in visited or real_path in import_chain:
                        continue

                    visited.add(key)
                    imported_files.add(real_path)
                    parsed_file = self.parse_file(path)

                    if parsed_file:
                        collect(parsed_file, import_namespaces, import_chain + (real_path,))

        collect(parsed, (), (real_file_path(filepath),) if filepath else ())

        return (declarations, imported_files)

    def imported_files(self, parsed, basepath, filepath = None):
        '''Returns the real paths of all files imported by parsed source code, resolved the same way as the compiler'''
        return self.walk(parsed, basepath, filepath, guess_paths = False)[1]

    def find_importer(self, filepath, scripts):
        '''Returns the path of the first script that imports filepath (directly or through other imports), or None.
           scripts is an iterable of (script path, parsed source code) tuples'''
        real_path = real_file_path(filepath)

        for script_path, parsed in scripts:
            if real_file_path(script_path) == real_path:
                continue

            if real_path in self.imported_files(parsed, os.path.dirname(script_path), script_path):
                return script_path

        return None

    def scan(self, source, basepath, filepath = None, parsed = None, guess_paths = True):
        '''Returns the declarations in source and in all files it imports'''
        if parsed is None:
            parsed = parse_source(source)

        declarations = self.walk(parsed, basepath, filepath, guess_paths)[0]

        # the same declaration can be reached through several imports, only list it once
        unique = collections.OrderedDict()

        for d in declarations:
            unique.setdefault((d.name, tuple(d.params), d.has_parens), d)

        return list(unique.values())
