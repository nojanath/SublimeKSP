from trieregex.trieregex import TrieRegEx as TRE
import fileinput
import os
import re
import sys

constants    = set()
variables    = set()
functions    = set()
control_pars = set()
event_pars   = set()

data = {
           'constants'    : constants,
           'variables'    : variables,
           'functions'    : functions,
           'control_pars' : control_pars,
           'event_pars'   : event_pars,
       }

section = None

sys.path.append('../compiler')

from ksp_builtins_data import builtins_data

lines = builtins_data.replace('\r\n', '\n').split('\n')

for line in lines:
    line = line.strip()

    if line.startswith('['):
        section = line[1:-1].strip()
    elif line:
        if section in data:
            if section == 'functions':
                m = re.match(r'(?P<name>\w+)\(?', line)
                data[section].add(m.group('name'))
                continue

            if section == 'constants':
                m = re.match(r'(?P<control_par>\$CONTROL_PAR_\w+?)|(?P<event_par>\$EVENT_PAR_\w+?)', line)

                if m:
                    control_par, event_par = m.group('control_par'), m.group('event_par')

                    if control_par:
                        control_pars.add(line)
                    elif event_par:
                        event_pars.add(line)

            data[section].add(line)

natsort = lambda s: [int(t) if t.isdigit() else t.lower() for t in re.split(r'(\d+)', s)]

all_builtins = sorted(list(constants.union(variables)), key=natsort)
all_functions = sorted(list(functions), key=natsort)
control_pars = sorted(list(control_pars), key=natsort)
event_pars = sorted(list(event_pars), key=natsort)

prefixes = '$@~%!?'

_int = list()
_real = list()
_str = list()
_intarray = list()
_strarray = list()

builtins = {
                '$' : _int,
                '~' : _real,
                '@' : _str,
                '%' : _intarray,
                '!' : _strarray,
            }

for item in all_builtins:
    if item[0] in prefixes:
        builtins[item[0]].append(item[1:])

cp         = ''
ep         = ''
funs       = ''
constsvars = ''

for p in builtins:
    b_trie = TRE(*builtins[p])

    prefix = p

    if p == '$':
        prefix = '\\$'

    constsvars += f'({prefix})?\\b{b_trie.regex()}\\b'

    if p in '$~@%':
        constsvars += '|'

f_trie = TRE(*all_functions)
f_trie.add('float')
funs = f'\\b{f_trie.regex()}\\b'

remap = {
            'pos_x' : 'x',
            'pos_y' : 'y',
            'max_value' : 'max',
            'min_value' : 'min',
            'default_value' : 'default',
            '0' : 'par_0',
            '1' : 'par_1',
            '2' : 'par_2',
            '3' : 'par_3',
        }

def extract_par_shorthands(par_list, remap):
    pars = []

    for i, item in enumerate(par_list):
        m = re.match(r'(\$CONTROL_PAR_|\$EVENT_PAR_)(?P<par>\w+)', item)

        if m:
            p = m.group('par').lower()

            pars.append(p)

            if p in remap:
                pars.append(remap[p])

    return pars

cp = extract_par_shorthands(control_pars, remap)
ep = extract_par_shorthands(event_pars, remap)

s_tre = TRE(*cp)
s_tre.add(*ep)

shorthands = s_tre.regex()

with fileinput.input('../KSP.sublime-syntax', inplace = True) as f:
    for line in f:
        if line.startswith('  builtin_const'):
            modified_line = f'  builtin_consts_and_vars: \'{constsvars}\''
            print(modified_line)
        elif line.startswith('  builtin_fun'):
            modified_line = f'  builtin_functions: \'{funs}\''
            print(modified_line)
        elif line.startswith('  builtin_par'):
            modified_line = f'  builtin_param_shorthands: \'(->)\\s*({shorthands})\\b\''
            print(modified_line)
        else:
            print(line, end = '')