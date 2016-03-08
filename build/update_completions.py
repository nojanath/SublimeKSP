import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), 'ksp_compiler3'))
from ksp_compiler3.ksp_builtins import *

out = open('ksp.sublime-completions', 'w')

out.write('''{
    "scope": "source.ksp",

    "completions":
    [
''')

vars = [v[1:] for v in variables]
for v in vars:
    out.write('        "%s",\n' % v)

for f in functions:
    args = ['${%d:%s}' % (i+1, a.replace('number variable or text', '').replace('-', '_')) for i, a in enumerate(function_signatures[f][0])]
    if args:
        args = '(%s)' % ', '.join(args)
    else:
        args = ''
    out.write('        { "trigger": "%s\\t%s", "contents": "%s%s"},\n' % (f, f, f, args))
    #{"trigger":"eval\teval description", "contents": "eval(${1:expression}${2:, ${3:globals}${4:, ${5:locals}}})"},

out.write('        ]\n')
out.write('}')

