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

import re
import os.path
import pkgutil

variables = set()
functions = set()
keywords = set()
string_typed_control_parameters = set()
function_signatures = {}
functions_with_forced_parenthesis = set()

data = {'variables': variables,
        'functions': functions,
        'keywords':  keywords,
        'string_typed_control_parameters': string_typed_control_parameters,
        'functions_with_forced_parenthesis': functions_with_forced_parenthesis}

section = None
try:
    builtins_data = pkgutil.get_data('ksp_compiler', 'builtins.txt')
    if builtins_data is None:
        builtins_data = open('ksp_builtins.txt', 'r').read()
except:
    from ksp_builtins_data import builtins_data
    #builtins_data = open('ksp_builtins.txt', 'r').read()
lines = builtins_data.replace('\r\n', '\n').split('\n')
##lines = open('builtins.txt', 'r').read().replace('\r\n', '\n').split('\n')
for line in lines:
    line = line.strip()
    if line.startswith('['):
        section = line[1:-1].strip()
    elif line:
        data[section].add(line)

        if section == 'functions':
            m = re.match(r'(?P<name>\w+)(\((?P<params>.*?)\))?(:(?P<return_type>\w+))?', line)
            name, params, return_type = m.group('name'), m.group('params'), m.group('return_type')
            params = [p.strip() for p in params.replace('<', '').replace('>', '').split(',') if p.strip()]
            function_signatures[name] = (params, return_type)

# mapping from function_name to descriptive string
functions = dict([(x.split('(')[0], x) for x in functions])
variables_unprefixed = set([v[1:] for v in variables])
keywords = set(keywords).union(set(['async_complete']))
