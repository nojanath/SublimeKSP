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
from ksp_ast import ParseException

def ReturnParam(i=1):
    def func(p):
        return p[i]
    return func

def ReturnNone(p):
    return None

def EmptyList(p):
    return []

def AddToList(item_index=1, list_index=2, dont_add_none=False):
    def func(p):
        if dont_add_none and p[item_index] is None:
            return p[list_index]
        else:
            return [p[item_index]] + p[list_index]
    return func

def AddToEmptyList(item_index=1, dont_add_none=False):
    def func(p):
        if dont_add_none and p[item_index] is None:
            return []
        else:
            return [p[item_index]]
    return func

def raise_parse_exception(p, msg, error_token=-1):
    try:
        token = p[error_token]
    except TypeError:
        token = p
    raise ParseException(token, msg)

def RaiseParseException(msg='Syntax error', error_token=-1):
    def func(p):
        emsg = msg
        if error_token:
            try:
                token = p[error_token]
            except TypeError:
                token = p
            #emsg = emsg + '\nat line: %d' % token.lineno
        raise ParseException(token, emsg)
    return func

last_rule = None
module = None

def g(rule, func):
    global last_rule
    global module

    # figure out the module of the calling function by examining stack frames and cache it
    if module is None:
        try:
            raise RuntimeError()
        except RuntimeError as e:
            e, b, t = sys.exc_info()
            f = t.tb_frame
            f = f.f_back           # Walk out to our calling function
            module = sys.modules[f.f_locals['__name__']] # grab name of module and look it up

    if not ':' in rule and not rule.lstrip()[0] == '|':
        raise Exception("Error in rule, it doesn't begin with | and contains no :")
    # make it possible to write several | on the same line
    if rule.count('\n') == 0:
        rule = rule.replace('|', '\n|')
    if not ':' in rule:
        rule = rule.replace('|', '%s :' % last_rule, 1)
    else:
        last_rule = rule[:rule.index(' ')]
    name = 'p_' + last_rule

    def new_func(p):
        r = func(p)
        p[0] = r

    #dict = sys.modules[__name__].__dict__
    dict = module.__dict__  # access namespace of calling module
    if name in dict:
        # change name of earlier func (eg. test -> test_1)
        dict[name].__name__ = '%s_1' % name
        dict['%s_1' % name] = dict[name]     # link new name (test_1) to the earlier func
        del dict[name]                       # delete the link to the earlier name (test)
    if '%s_1' % name in dict:
        # find unused name for new func (eg. test_2, test_3 or test_4 ...)
        i = 2
        while '%s_%d' % (name, i) in dict:
            i += 1
        name = '%s_%d' % (name, i)
    dict[name] = new_func
    new_func.__name__ = name
    new_func.__doc__ = rule
    return new_func

