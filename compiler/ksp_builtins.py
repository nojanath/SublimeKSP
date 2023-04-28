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
control_parameters = set()
string_typed_control_parameters = set()
engine_parameters = set()
event_parameters = set()
function_signatures = {}
functions_with_forced_parentheses = set()
functions_with_constant_return = set() # Functions with return values that can be used for const variables
functions_evaluated_with_optimize_code = set() # Functions that can be evaluated during compiling when optimize_code is enabled
ui_control_signatures = {}

sKSP_preprocessor_variables = ("sksp_dummy", "string_it", "list_it", "concat_it", "concat_offset", "preproc_i")

data = {'variables': variables,
        'functions': functions,
        'keywords':  keywords,
        'control_parameters': control_parameters,
        'string_typed_control_parameters': string_typed_control_parameters,
        'engine_parameters': engine_parameters,
        'event_parameters' : event_parameters,
        'functions_with_forced_parentheses': functions_with_forced_parentheses,
        'functions_with_constant_return': functions_with_constant_return,
        'functions_evaluated_with_optimize_code': functions_evaluated_with_optimize_code,
        'sKSP_variables' : sKSP_preprocessor_variables,
        }

section = None

from ksp_builtins_data import builtins_data

lines = builtins_data.replace('\r\n', '\n').split('\n')

for line in lines:
    line = line.strip()

    if line.startswith('['):
        section = line[1:-1].strip()
    elif line:
        if section in data:
            data[section].add(line)

        if section == 'functions':
            m = re.match(r'(?P<name>\w+)(\(+(?P<params>.*?)\)+)?(:(?P<return_type>\w+))?', line)
            name, params, return_type = m.group('name'), m.group('params'), m.group('return_type')
            params = [p.strip() for p in params.replace('<', '').replace('>', '').split(',') if p.strip()] if params else ''

            # if a function has overloads, append the (params, return_type) set to the value list
            if name in function_signatures:
                function_signatures[name].append((params, return_type))
            else:
                function_signatures[name] = [(params, return_type)]

            if name not in functions_with_constant_return and (return_type == "real" or return_type == "integer"):
                functions_with_constant_return.add(name)

        if section == 'variables':
            m = re.match(r'(?P<control_par>\$CONTROL_PAR_\w+?)|(?P<engine_par>\$ENGINE_PAR_\w+?)|(?P<event_par>\$EVENT_PAR_\w+?)', line)

            if m:
                control_par, engine_par, event_par = m.group('control_par'), m.group('engine_par'), m.group('event_par')

                if control_par:
                    control_parameters.add(line)
                elif engine_par:
                    engine_parameters.add(line)
                elif event_par:
                    event_parameters.add(line)

        if section == 'ui_control_signatures':
            m = re.match(r'(?P<ui_control>\w+)\s+(?P<identifier>[$%!~@?]<[^>]+>)\s*(?P<size>\[[^]]*\])?\s*(\((?P<params>.*)\))?', line)
            ui_ctrl, params = m.group('ui_control'), m.group('params')

            if params:
                params = [p.strip() for p in params.replace('<', '').replace('>', '').split(',') if p.strip()]
            else:
                params = []

            ui_control_signatures[ui_ctrl] = params

# mapping from function_name to descriptive string
functions = dict([(x.split('(')[0], x) for x in functions])
variables_unprefixed = set([v[1:] for v in variables])
