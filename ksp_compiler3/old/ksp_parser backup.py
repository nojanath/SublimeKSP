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

import ply.lex as lex
import ply.yacc as yacc
import re
from parser_utils import *
from ksp_ast import *
from ksp_ast_processing import *
import os
import os.path

# *********************************** LEXER *******************************************

reserved = (
    'FUNCTION', 'TASKFUNC', 'AND', 'OR', 'NOT', 'IF', 'TO', 'DOWNTO', 'ELSE', 'FOR', 'WHILE', 'DECLARE',
    'SELECT', 'CASE', 'CONST', 'POLYPHONIC', 'END', 'LOCAL', 'GLOBAL', 'FAMILY', 'IMPORT', 'AS', 'PROPERTY',
    'UI_LABEL', 'UI_BUTTON', 'UI_SWITCH', 'UI_SLIDER', 'UI_MENU', 'UI_VALUE_EDIT', 'UI_WAVEFORM', 'UI_KNOB', 'UI_TABLE', 'CALL', 'STEP',
    'UI_TEXT_EDIT', 'UI_LEVEL_METER', 'UI_FILE_SELECTOR', 'OVERRIDE',
    )
reserved_map = dict(((r.lower(), r) for r in reserved))
reserved_map['SET_CONDITION'] = 'SET_CONDITION'
reserved_map['RESET_CONDITION'] = 'RESET_CONDITION'

tokens = reserved + (
    'BEGIN_CALLBACK', 'END_CALLBACK',
    'SET_CONDITION', 'RESET_CONDITION',
    'RIGHTARROW', 'PLUS', 'MINUS', 'TIMES', 'DIVIDE', 'MOD', 'BITWISE_AND', 'BITWISE_OR', 'BITWISE_NOT', 'COMPARE', 'CONCAT', 'ASSIGN',
    'LPAREN', 'RPAREN', 'LBRACK', 'RBRACK',
    'ID',
    'NUMBER', 'STRING',
    'INIT_ARRAY',
    'COMMA', 'DOT', 'LINECONT', 'NEWLINE', 'COMMENT'
    )

t_RIGHTARROW = '->'
t_PLUS, t_MINUS, t_TIMES, t_DIVIDE = [re.escape(op) for op in '+ - * /'.split()]
t_LPAREN, t_RPAREN, t_LBRACK, t_RBRACK = [re.escape(op) for op in '()[]']
t_COMPARE = '|'.join([re.escape(op) for op in '<= >= < > # ='.split()])
t_COMMA  = ','
t_DOT    = r'\.'
t_CONCAT = '&'
t_ASSIGN = ':='
t_STRING = r"'.*?(?<!\\)'|" + r'".*?(?<!\\)"'
t_SET_CONDITION = 'SET_CONDITION'
t_RESET_CONDITION = 'RESET_CONDITION'

hex_number_re1 = re.compile('0x[a-fA-f0-9]+$')
hex_number_re2 = re.compile('[0-9][a-fA-f0-9]*[hH]$')
number_re = re.compile('-?\d+')

# define bitwise and/or/not as functions to make sure they are tried before the ID token
def t_BITWISE_AND(t):
    r'\.and\.'
    return t

def t_BITWISE_OR(t):
    r'\.or\.'
    return t

def t_BITWISE_NOT(t):
    r'\.not\.'
    return t

def t_BEGIN_CALLBACK(t):
    r'on\s+(init|note|release|midi_in|controller|rpn|nrpn|ui_update|_pgs_changed|pgs_changed|poly_at|listener|async_complete|(ui_control\s*?\(.+?\)))'
    t.type = 'BEGIN_CALLBACK'
    ui_control = None
    s = re.sub(r'ui_control\s*', 'ui_control', t.value)
    parts = s.split()
    name = parts[1]
    if name.startswith('ui_control'):
        ui_control = re.match(r'on\s+ui_control\s*?\((.+)\)', t.value).group(1).strip()
        name = 'ui_control'
    t.value = {'name': name, 'ui_control': ui_control}
    return t

def t_END_CALLBACK(t):
    r'end\s+on'
    t.type = 'END_CALLBACK'
    return t

def t_ID(t):
    r'[$%!@][A-Za-z0-9_.]+|[A-Za-z_][A-Za-z0-9_.]*|\d+[A-Za-z_][A-Za-z0-9_]*'
    if t.value == 'mod': # mod operator
        t.type = 'MOD'
    elif t.value.startswith('0x') and hex_number_re1.match(t.value): # hex number, eg. 0x10
        t.type = 'NUMBER'
        t.value = int(t.value, 16)
    elif (t.value.endswith('h') or t.value.endswith('H')) and hex_number_re2.match(t.value): # hex number, eg. 010h
        t.type = 'NUMBER'
        t.value = int(t.value[:-1], 16)
    else:
        t.type = reserved_map.get(t.value,"ID")
    return t

def t_NUMBER(t):
    r'\d+'
    try:
        t.value = int(t.value)
    except ValueError:
        print("Line %d: Number %s is too large!" % (t.lineno,t.value))
        t.value = 0
    return t

def t_INIT_ARRAY(t):
    r'\(\s*-?\d+\s*(,(\s*\.\.\.)?\s*-?\d+\s*)+\)'
    t.value = re.sub(r'[^-0-9,]', '', t.value)
    return t

def InitArrayToList(lexinfo, init_array_token):
    return [Number(lexinfo, int(num)) for num in number_re.findall(init_array_token)]

def t_MOD(t):
    'mod'
    return t

def t_error(t):
    ##print "Illegal character '%s'" % t.value[0], t.lineno
    t.lexer.skip(1)

t_ignore  = ' \t'

# Define a rule so we can track line numbers
def t_NEWLINE(t):
    r'\n'
    t.lexer.lineno += 1
    return t

def t_COMMENT(t):
    r'\{[^}]*?\}|\(\*[\w\W]*?\*\)'
    t.lexer.lineno += t.value.count('\n')
    pass

def t_LINECONT(t):
    r'\.\.\.[ \t]*\n'
    t.lexer.lineno += 1
    pass

##lex.lex()

# *********************************** PARSER *******************************************

precedence = (
    ('nonassoc', 'LPAREN', 'RPAREN'),
    ('nonassoc', 'ASSIGN'),
    ('left', 'CONCAT'),
    ('left', 'OR'),
    ('left', 'AND'),
    ('right', 'NOT'),
    ('nonassoc', 'COMPARE'),
    ('left', 'BITWISE_AND', 'BITWISE_OR'),
    ('right', 'BITWISE_NOT'),
    ('left', 'PLUS', 'MINUS'),
    ('left', 'TIMES', 'DIVIDE', 'MOD'),
    ('right', 'UMINUS'),
    ('right', 'DOT'),
)

# grammar:
# ---------------------------------------------------------------------------------

g('script                : newlines-opt toplevels', lambda p: Module(p, blocks=p[2]))
g('                      | newlines-opt error    ', RaiseParseException('syntax error'))
g('toplevels             : toplevel toplevels', AddToList())
g('                      | empty             ', EmptyList)
g('''toplevel            : callback newlines-opt
                         | functiondef newlines-opt
                         | import newlines-opt''', ReturnParam())

g('newlines-opt          : newlines-opt NEWLINE | empty', ReturnNone)

g('callback              : BEGIN_CALLBACK NEWLINE stmts-opt END_CALLBACK', lambda p: Callback(p, p[1]['name'], p[3], p[1]['ui_control']))

g('import                : IMPORT STRING         ', lambda p: Import(p, p[2]))
g('                      | IMPORT STRING AS ident', lambda p: Import(p, p[2], p[4]))

g('functiondef           : FUNCTION ident params-opt          return-value-opt override-opt NEWLINE stmts-opt END FUNCTION', lambda p: FunctionDef(p, p[2], p[3], p[4], p[7], override=p[5]))
g('                      | TASKFUNC ident taskfunc-params-opt return-value-opt override-opt NEWLINE stmts-opt END TASKFUNC', lambda p: FunctionDef(p, p[2], p[3], p[4], p[7], override=p[5], is_taskfunc=True))
g('return-value-opt      : RIGHTARROW ident', ReturnParam(i=2))
g('                      | empty', ReturnNone)
g('override-opt          : OVERRIDE', lambda p: True)
g('                      | empty   ', lambda p: False)

g('stmts-opt             : stmts', ReturnParam())
g('                      | empty', EmptyList)  # changed

g('stmts                 : stmt      ', AddToEmptyList(dont_add_none=True))
g('                      | stmt stmts', AddToList(dont_add_none=True))

g('''stmt                : declaration NEWLINE
                         | propertydef NEWLINE
                         | family-declaration NEWLINE
                         | assignment NEWLINE
                         | preprocessor-stmt NEWLINE
                         | procedure-call NEWLINE
                         | if-stmt NEWLINE
                         | while-stmt NEWLINE
                         | for-stmt NEWLINE
                         | select-stmt NEWLINE
                         | set-ui-par-stmt NEWLINE''', ReturnParam())
g('                      | NEWLINE | dummy      ', ReturnNone)
#g('                      | error                ', RaiseParseException())

g('preprocessor-stmt     : SET_CONDITION LPAREN ID RPAREN',   lambda p: PreprocessorCondition(p, p[1], p[3]))
g('                      | RESET_CONDITION LPAREN ID RPAREN', lambda p: PreprocessorCondition(p, p[1], p[3]))

g('if-stmt               : IF expression NEWLINE stmts-opt else-if-opt END IF', lambda p: IfStmt(p, condition_stmts_tuples = [(p[2], p[4])] + p[5]))
g('                      | IF expression NEWLINE stmts-opt else-if-opt error ', RaiseParseException("Expected 'end if'"))
g('else-if-opt           : ELSE else-if-condition-opt NEWLINE stmts-opt else-if-opt', lambda p: [(p[2], p[4])] + p[5]) # [(condition, stmts), ...]
g('                      | empty                                                        ', EmptyList)
g('else-if-condition-opt : IF expression', ReturnParam(2))
g('                      | empty        ', ReturnNone)  # condition is None for else statements (not else if)

g('while-stmt            : WHILE expression NEWLINE stmts-opt END WHILE', lambda p: WhileStmt(p, p[2], p[4]))
g('                      | WHILE expression NEWLINE stmts-opt error    ', RaiseParseException("Expected 'end while'"))
g('for-stmt              : FOR varref ASSIGN expression updownto expression NEWLINE stmts-opt END FOR', lambda p: ForStmt(p, p[2], p[4], p[6], p[8], downto=p[5]))
g('                      | FOR varref ASSIGN expression updownto expression STEP expression NEWLINE stmts-opt END FOR', lambda p: ForStmt(p, p[2], p[4], p[6], p[10], downto=p[5], step=p[8]))
g('                      | FOR varref ASSIGN expression updownto expression NEWLINE stmts-opt error  ', RaiseParseException("Expected 'end for'"))
g('updownto              : TO | DOWNTO', lambda p: p[1] == 'downto') # True if 'downto', False if 'to'

g('select-stmt           : SELECT expression NEWLINE select-cases END SELECT', lambda p: SelectStmt(p, p[2], p[4]))
g('                      | SELECT expression NEWLINE select-cases error     ', RaiseParseException("Expected 'end select'"))
g('select-cases          : select-case select-cases', AddToList())
g('                      | empty                   ', EmptyList)
g('select-case           : newlines-opt CASE expression NEWLINE stmts-opt              ', lambda p: ((p[3], None), p[5])) # ((range_start, range_end), stmts)
g('                      | newlines-opt CASE expression TO expression NEWLINE stmts-opt', lambda p: ((p[3], p[5]), p[7])) # ((range_start, range_end), stmts)
g('select-case           : newlines-opt ELSE NEWLINE stmts-opt                         ', lambda p: ((Number(p, 0x80000000), Number(p, 0x7FFFFFFF)), p[4])) # ((range_start, range_end), stmts), min_int to max_int

g('params-opt            : params', ReturnParam())
g('                      | empty ', EmptyList)
g('params                : LPAREN ID more-params-opt RPAREN', AddToList(2, 3))
g('                      | LPAREN RPAREN', EmptyList)
g('                      | INIT_ARRAY', lambda p: InitArrayToList(p, p[1]))
g('more-params-opt       : COMMA ID more-params-opt', AddToList(2, 3))
g('                      | empty                   ', EmptyList)

g('taskfunc-params-opt   : taskfunc-params', ReturnParam())
g('                      | empty     ', EmptyList)
g('taskfunc-params       : LPAREN    ID more-taskfunc-params-opt RPAREN', lambda p: [(None, p[2])] + p[3])
g('                      | LPAREN ID ID more-taskfunc-params-opt RPAREN', lambda p: [(p[2], p[3])] + p[4])
g('                      | LPAREN RPAREN                                ', EmptyList)
g('more-taskfunc-params-opt : COMMA    ID more-taskfunc-params-opt', lambda p: [(None, p[2])] + p[3])
g('                         | COMMA ID ID more-taskfunc-params-opt', lambda p: [(p[2], p[3])] + p[4])
g('                         | empty                               ', EmptyList)

g('args-opt              : args', ReturnParam())
g('                      | empty ', EmptyList)
g('args                  : LPAREN expression more-args-opt RPAREN', AddToList(2, 3))
g('                      | INIT_ARRAY', lambda p: InitArrayToList(p, p[1]))
g('                      | LPAREN RPAREN', EmptyList)
g('more-args-opt         : COMMA expression more-args-opt', AddToList(2, 3))
g('                      | empty                         ', EmptyList)

g('function-call         : ident args    ', lambda p: FunctionCall(p, function_name=p[1], parameters=p[2]))
g('                      | CALL ident args-opt', lambda p: FunctionCall(p, function_name=p[2], parameters=p[3], is_procedure=False, using_call_keyword=True))
g('procedure-call        : ident args-opt', lambda p: FunctionCall(p, function_name=p[1], parameters=p[2], is_procedure=True))
g('                      | CALL ident args-opt', lambda p: FunctionCall(p, function_name=p[2], parameters=p[3], is_procedure=True, using_call_keyword=True))

g('propertydef           : PROPERTY ident NEWLINE newlines-opt functiondefs END PROPERTY', lambda p: PropertyDef(p, p[2], functions=p[5]))
g('                      | PROPERTY ident id-subscripts-opt RIGHTARROW varref',               lambda p: PropertyDef(p, p[2], indices=p[3], alias_varref=p[5]))
g('functiondefs          : functiondef newlines-opt',              AddToEmptyList(item_index = 1, dont_add_none=True))
g('                      | functiondef newlines-opt functiondefs', AddToList(item_index = 1, list_index = 3, dont_add_none=True))

g('declaration           : DECLARE global-modifier-opt decl-modifier-opt ident args-opt initial-value-opt', lambda p: DeclareStmt(p, variable=p[4], modifiers=p[2] + p[3], size=None, parameters=p[5], initial_value=p[6]))
g('                      | DECLARE global-modifier-opt decl-modifier-opt ident array-size args-opt initial-array-opt', lambda p: DeclareStmt(p, variable=p[4], modifiers=p[2] + p[3], size=p[5], parameters=p[6], initial_value=p[7]))
g('family-declaration    : FAMILY ident NEWLINE stmts-opt END FAMILY', lambda p: FamilyStmt(p, name=p[2], statements=p[4]))
g('                      | FAMILY ident NEWLINE stmts-opt error     ', RaiseParseException("Expected 'end family'"))
g('global-modifier-opt   : LOCAL | GLOBAL', AddToEmptyList())
g('                      | empty         ', EmptyList)
g('decl-modifier-opt     : CONST | POLYPHONIC | UI_LABEL | UI_BUTTON | UI_SWITCH | UI_SLIDER | UI_MENU | UI_KNOB | UI_TABLE | UI_VALUE_EDIT | UI_WAVEFORM | UI_TEXT_EDIT | UI_LEVEL_METER | UI_FILE_SELECTOR | ', AddToEmptyList())
g('                      | empty             ', EmptyList)
g('initial-value-opt     : ASSIGN expression     ', ReturnParam(2))
g('                      | empty                 ', ReturnNone)
g('initial-array-opt     : ASSIGN args           ', ReturnParam(2))
g('                      | ASSIGN INIT_ARRAY     ', lambda p: RawArrayInitializer(p, p[2]))
g('                      | empty                 ', ReturnNone)
g('array-size            : LBRACK expression RBRACK', ReturnParam(2))

g('set-ui-par-stmt       : varref RIGHTARROW ident ASSIGN expression',   lambda p: handle_set_control_par(p[1], p[3], p[5]))
g('get-ui-par-expr       : varref RIGHTARROW ident',                     lambda p: handle_get_control_par(p[1], p[3]))

#g('basic-varref          : ident                      ', ReturnParam())
#g('                      | basic-varref DOT ident     ', lambda p: '%s.%s' % (p[1], p[3]))

g('subscripts            : LBRACK expression more-subscripts-opt RBRACK', AddToList(2, 3))
g('more-subscripts-opt   : COMMA expression more-subscripts-opt        ', AddToList(2, 3))
g('                      | empty                                       ', EmptyList)

g('id-subscripts-opt      : id-subscripts', ReturnParam(1))
g('id-subscripts-opt      : empty',         EmptyList)
g('id-subscripts          : LBRACK ident more-id-subscripts-opt RBRACK', AddToList(2, 3))
g('more-id-subscripts-opt : COMMA ident more-id-subscripts-opt        ', AddToList(2, 3))
g('                       | empty                                     ', EmptyList)

g('basic-varref          : ident                         ', lambda p: VarRef(p, identifier=p[1]))
g('                      | ident subscripts              ', lambda p: VarRef(p, identifier=p[1], subscripts=p[2]))
g('varref                : basic-varref                  ', lambda p: p[1])
g('                      | basic-varref DOT varref       ', lambda p: VarRef(p, ID(p, identifier='%s.%s' % (p[1].identifier, p[3].identifier)),
                                                                                subscripts=p[1].subscripts + p[3].subscripts))

g('assignment            : varref ASSIGN expression', lambda p: AssignStmt(p, p[1], p[3]))

g('literal               : NUMBER', lambda p: Number(p, p[1]))
g('                      | STRING', lambda p: String(p, p[1]))

g('''expression          : expression PLUS expression
                         | expression MINUS expression
                         | expression TIMES expression
                         | expression DIVIDE expression
                         | expression MOD expression
                         | expression BITWISE_AND expression
                         | expression BITWISE_OR expression
                         | expression COMPARE expression
                         | expression AND expression
                         | expression OR expression
                         | expression CONCAT expression ''', lambda p: BinOp(p, p[1], p[2], p[3]))
g('''                    | NOT expression
                         | BITWISE_NOT expression
                         | MINUS expression %prec UMINUS''', lambda p: UnaryOp(p, p[1], p[2]))
g('''                    | LPAREN expression RPAREN     ''', ReturnParam(2))
g('''                    | literal
                         | varref
                         | function-call
                         | get-ui-par-expr              ''',ReturnParam(1))

g('ident                 : ID', lambda p: ID(p, p[1]))

g('dummy                 : COMMENT | LINECONT', lambda p: 'Dummy(%s)' % p[1])
g('empty                 :                   ', ReturnParam(0))
g('error                 :                   ', RaiseParseException())

def init(outputdir=None):
    outputdir = outputdir or os.path.dirname(__file__)  # os.getcwd()
    current_module = sys.modules[__name__]
    #print (outputdir, current_module)
    debug = 1
    optimize = 0
    lexer = lex.lex(optimize=0, debug=debug)
    return yacc.yacc(method="LALR", optimize=optimize, debug=debug,
                     write_tables=1, module=current_module, start='script',
                     outputdir=outputdir, tabmodule='ksp_parser_tab')

parser = init()


def parse(script_code):
    lex.lexer.lineno = 0
    lex.lexer.filename = 'current file'  # filepath
    data = script_code.replace('\r', '')
    result = parser.parse(data, tracking=True)
    return result

##import os
##visitor = ASTVisitorDotGenerator(module)
##open('output.dot', 'w').write(visitor.get_dot_output())
##os.system(r'"C:\Program Files\Graphviz\Graphviz\bin\dot.exe" -Tpng output.dot -o output.png')
