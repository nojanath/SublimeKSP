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

import sys
from time import strftime, localtime

try:
    from sublime import status_message
    has_sublime_api = True
except ImportError:
    has_sublime_api = False

def disable_traceback():
    if sys.version_info < (3, 6, 2):
        sys.tracebacklimit = None
    else:
        sys.tracebacklimit = 0

def split_args(arg_string, line):
    '''converts eg. "x, y*(1+z), z" into a list ['x', 'y*(1+z)', 'z']'''
    if arg_string.strip() == '':
        return []
    args = []
    cur_arg = ''
    unmatched_left_paren = 0
    double_quote_on = False

    for idx, ch in enumerate(arg_string + ','):    # extra ',' to include the last argument
        # square brackets are also checked as there may be commas in them (for properties/2D arrays)
        if ch == '\"' and (idx == 0 or arg_string[idx - 1] != '\\'):
            double_quote_on = not double_quote_on
        elif ch in ['(', '[']:
            unmatched_left_paren += 1
        elif ch in [')', ']']:
            unmatched_left_paren -= 1
        if ch == ',' and unmatched_left_paren == 0 and not double_quote_on:
            cur_arg = cur_arg.strip()
            if not cur_arg:
                from ksp_compiler import ParseException
                raise ParseException(line, 'Empty argument in function call %s!' % arg_string, True)
            args.append(cur_arg)
            cur_arg = ''
        else:
            cur_arg += ch
    if unmatched_left_paren:
        from ksp_compiler import ParseException
        raise ParseException(line, 'Unmatched parenthesis in function call %s!' % arg_string, True)
    return args

def log_message(msg):
    txt = "{0}: {1}".format(strftime('%X', localtime()), msg)

    if has_sublime_api:
        txt = "[SublimeKSP] " + txt
        print(txt)
        status_message(txt)
    else:
        print(txt)

def compile_on_progress(text, percent_complete):
    log_message('Compiling (%d%%) - %s...' % (percent_complete, text))
