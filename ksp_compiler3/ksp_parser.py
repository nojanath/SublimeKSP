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

#t_RIGHTARROW = '->'
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
    r'on\s+(init|note|release|midi_in|controller|rpn|nrpn|ui_update|_pgs_changed|pgs_changed|poly_at|listener|async_complete|persistence_changed|persistence_changed|(ui_control\s*?\(.+?\)))'
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

def t_RIGHTARROW(t):
    r'->'
    t.type = 'RIGHTARROW'
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
        t.type = reserved_map.get(t.value, "ID")
    return t

def t_NUMBER(t):
    r'\d+'
    try:
        t.value = int(t.value)
    except ValueError:
        print("Line %d: Number %s is too large!" % (t.lineno, t.value))
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

def p_script(p):
    'script               : newlines-opt toplevels'
    p[0] = Module(p, blocks=p[2])

def p_script_error(p):
    'script               : newlines-opt error'
    raise_parse_exception(p, 'syntax error')

def p_toplevels(p):
    'toplevels             : toplevel toplevels'
    p[0] = [p[1]] + p[2]

def p_toplevels_empty(p):
    'toplevels             : empty'
    p[0] = []

def p_toplevel(p):
    '''toplevel            : callback newlines-opt
                           | functiondef newlines-opt
                           | import newlines-opt'''
    p[0] = p[1]

def p_newlines_opt(p):
    '''newlines-opt        : NEWLINE newlines-opt
                           | empty'''
    p[0] = None

def p_callback(p):
    'callback              : BEGIN_CALLBACK NEWLINE stmts-opt END_CALLBACK'
    p[0] = Callback(p, p[1]['name'], p[3], p[1]['ui_control'])

def p_import(p):
    'import                : IMPORT STRING'
    p[0] = Import(p, p[2])

def p_import_as(p):
    'import                : IMPORT STRING AS ident'
    p[0] = Import(p, p[2], p[4])

def p_functiondef(p):
    'functiondef           : FUNCTION ident params-opt          return-value-opt override-opt NEWLINE stmts-opt END FUNCTION'
    p[0] = FunctionDef(p, p[2], p[3], p[4], p[7], override=p[5])

def p_taskfuncdef(p):
    'functiondef           : TASKFUNC ident taskfunc-params-opt return-value-opt override-opt NEWLINE stmts-opt END TASKFUNC'
    p[0] = FunctionDef(p, p[2], p[3], p[4], p[7], override=p[5], is_taskfunc=True)

def p_return_value_opt(p):
    'return-value-opt      : RIGHTARROW ident'
    p[0] = p[2]

def p_return_value_opt_empty(p):
    'return-value-opt      : empty'
    p[0] = None

def p_override_opt(p):
    'override-opt          : OVERRIDE'
    p[0] = True

def p_override_opt_empty(p):
    'override-opt          : empty'
    p[0] = False

def p_stmts_opt(p):
    'stmts-opt             : stmts'
    p[0] = p[1]

def p_stmts_opt_empty(p):
    'stmts-opt             : empty'
    p[0] = []

def p_stmts(p):
    'stmts                 : stmt'
    if p[1] is None:
        p[0] = []
    else:
        p[0] = [p[1]]

def p_stmts_more(p):
    'stmts                 : stmt stmts'
    if p[1] is None:
        p[0] = p[2]
    else:
        p[0] = [p[1]] + p[2]

def p_stmt(p):
    '''stmt                : declaration NEWLINE
                           | propertydef NEWLINE
                           | family-declaration NEWLINE
                           | assignment NEWLINE
                           | preprocessor-stmt NEWLINE
                           | procedure-call NEWLINE
                           | if-stmt NEWLINE
                           | while-stmt NEWLINE
                           | for-stmt NEWLINE
                           | select-stmt NEWLINE
                           | set-ui-par-stmt NEWLINE'''
    p[0] = p[1]

def p_stmt_empty(p):
    '''stmt                : NEWLINE
                           | dummy'''
    p[0] = None

def p_preprocessor_stmt_set_condition(p):
    'preprocessor-stmt     : SET_CONDITION LPAREN ID RPAREN'
    p[0] = PreprocessorCondition(p, p[1], p[3])

def p_preprocessor_stmt_reset_condition(p):
    'preprocessor-stmt     : RESET_CONDITION LPAREN ID RPAREN'
    p[0] = PreprocessorCondition(p, p[1], p[3])

def p_if_stmt(p):
    'if-stmt               : IF expression NEWLINE stmts-opt else-if-opt END IF'
    p[0] = IfStmt(p, condition_stmts_tuples=[(p[2], p[4])] + p[5])

def p_if_stmt_error(p):
    'if-stmt               : IF expression NEWLINE stmts-opt else-if-opt error'
    raise_parse_exception(p, "Expected 'end if'")

def p_else_if_opt(p):
    'else-if-opt           : ELSE else-if-condition-opt NEWLINE stmts-opt else-if-opt'
    p[0] = [(p[2], p[4])] + p[5] # [(condition, stmts), ...

def p_else_if_opt_empty(p):
    'else-if-opt           : empty'
    p[0] = []

def p_else_if_condition_opt(p):
    'else-if-condition-opt : IF expression'
    p[0] = p[2]

def p_else_if_condition_opt_empty(p):
    'else-if-condition-opt : empty'
    p[0] = None  # condition is None for else statements (not else if)

def p_while_stmt(p):
    'while-stmt            : WHILE expression NEWLINE stmts-opt END WHILE'
    p[0] = WhileStmt(p, p[2], p[4])

def p_while_stmt_error(p):
    'while-stmt            : WHILE expression NEWLINE stmts-opt error'
    raise_parse_exception(p, "Expected 'end while'")

def p_for_stmt(p):
    'for-stmt              : FOR varref ASSIGN expression updownto expression NEWLINE stmts-opt END FOR'
    p[0] = ForStmt(p, p[2], p[4], p[6], p[8], downto=p[5])

def p_for_stmt_with_step(p):
    'for-stmt              : FOR varref ASSIGN expression updownto expression STEP expression NEWLINE stmts-opt END FOR'
    p[0] = ForStmt(p, p[2], p[4], p[6], p[10], downto=p[5], step=p[8])

def p_for_stmt_error(p):
    'for-stmt              : FOR varref ASSIGN expression updownto expression NEWLINE stmts-opt error'
    raise_parse_exception(p, "Expected 'end for'")

def p_updownto(p):
    '''updownto            : TO
                           | DOWNTO'''
    p[0] = (p[1] == 'downto') # True if 'downto', False if 'to

def p_select_stmt(p):
    'select-stmt           : SELECT expression NEWLINE select-cases END SELECT'
    p[0] = SelectStmt(p, p[2], p[4])

def p_select_stmt_error(p):
    'select-stmt           : SELECT expression NEWLINE select-cases error'
    raise_parse_exception(p, "Expected 'end select'")

def p_select_cases(p):
    'select-cases          : select-case select-cases'
    p[0] = [p[1]] + p[2]

def p_select_cases_empty(p):
    'select-cases          : empty'
    p[0] = []

def p_select_case(p):
    'select-case           : newlines-opt CASE expression NEWLINE stmts-opt'
    p[0] = ((p[3], None), p[5]) # ((range_start, range_end), stmts)

def p_select_case_with_range(p):
    'select-case           : newlines-opt CASE expression TO expression NEWLINE stmts-opt'
    p[0] = ((p[3], p[5]), p[7]) # ((range_start, range_end), stmts)

def p_select_case_else(p):
    'select-case           : newlines-opt ELSE NEWLINE stmts-opt'
    p[0] = ((Number(p, 0x80000000), Number(p, 0x7FFFFFFF)), p[4]) # ((range_start, range_end), stmts), min_int to max_in)

def p_params_opt(p):
    'params-opt            : params'
    p[0] = p[1]

def p_params_opt_empty(p):
    'params-opt            : empty'
    p[0] = []

def p_params(p):
    'params                : LPAREN ID more-params-opt RPAREN'
    p[0] = [p[2]] + p[3]

def p_params_none(p):
    'params                : LPAREN RPAREN'
    p[0] = []

def p_params_init_array(p):
    'params                : INIT_ARRAY'
    p[0] = InitArrayToList(p, p[1])

def p_more_params_opt(p):
    'more-params-opt       : COMMA ID more-params-opt'
    p[0] = [p[2]] + p[3]

def p_more_params_opt_empty(p):
    'more-params-opt       : empty'
    p[0] = []

def p_taskfunc_params_opt(p):
    'taskfunc-params-opt   : taskfunc-params'
    p[0] = p[1]

def p_taskfunc_params_opt_empty(p):
    'taskfunc-params-opt   : empty'
    p[0] = []

def p_taskfunc_params(p):
    'taskfunc-params       : LPAREN    ID more-taskfunc-params-opt RPAREN'
    p[0] = [(None, p[2])] + p[3]

def p_taskfunc_params_with_modifier(p):
    'taskfunc-params       : LPAREN ID ID more-taskfunc-params-opt RPAREN'
    p[0] = [(p[2], p[3])] + p[4]

def p_taskfunc_params_none(p):
    'taskfunc-params       : LPAREN RPAREN'
    p[0] = []

def p_more_taskfunc_params_opt(p):
    'more-taskfunc-params-opt : COMMA    ID more-taskfunc-params-opt'
    p[0] = [(None, p[2])] + p[3]

def p_more_taskfunc_params_with_modifier_opt(p):
    'more-taskfunc-params-opt : COMMA ID ID more-taskfunc-params-opt'
    p[0] = [(p[2], p[3])] + p[4]

def p_more_taskfunc_params_opt_empty(p):
    'more-taskfunc-params-opt : empty'
    p[0] = []

def p_args_opt(p):
    'args-opt              : args'
    p[0] = p[1]

def p_args_opt_empty(p):
    'args-opt              : empty'
    p[0] = []

def p_args(p):
    'args                  : LPAREN expression more-args-opt RPAREN'
    p[0] = [p[2]] + p[3]

def p_args_int_array(p):
    'args                  : INIT_ARRAY'
    p[0] = InitArrayToList(p, p[1])

def p_args_none(p):
    'args                  : LPAREN RPAREN'
    p[0] = []

def p_more_args_opt(p):
    'more-args-opt         : COMMA expression more-args-opt'
    p[0] = [p[2]] + p[3]

def p_more_args_opt_empty(p):
    'more-args-opt         : empty'
    p[0] = []

def p_function_call(p):
    'function-call         : ident args'
    p[0] = FunctionCall(p, function_name=p[1], parameters=p[2])

def p_function_call_with_call(p):
    'function-call         : CALL ident args-opt'
    p[0] = FunctionCall(p, function_name=p[2], parameters=p[3], is_procedure=False, using_call_keyword=True)

def p_procedure_call(p):
    'procedure-call        : ident args-opt'
    p[0] = FunctionCall(p, function_name=p[1], parameters=p[2], is_procedure=True)

def p_procedure_call_with_call(p):
    'procedure-call        : CALL ident args-opt'
    p[0] = FunctionCall(p, function_name=p[2], parameters=p[3], is_procedure=True, using_call_keyword=True)

def p_propertydef(p):
    'propertydef           : PROPERTY ident NEWLINE newlines-opt functiondefs END PROPERTY'
    p[0] = PropertyDef(p, p[2], functions=p[5])

def p_propertydef_simplified(p):
    'propertydef           : PROPERTY ident id-subscripts-opt RIGHTARROW varref'
    p[0] = PropertyDef(p, p[2], indices=p[3], alias_varref=p[5])

def p_functiondefs1(p):
    'functiondefs          : functiondef newlines-opt'
    if p[1] is None:
        p[0] = []
    else:
        p[0] = [p[1]]

def p_functiondefs2(p):
    'functiondefs          : functiondef newlines-opt functiondefs'
    if p[1] is None:
        p[0] = p[3]
    else:
        p[0] = [p[1]] + p[3]

def p_declaration1(p):
    'declaration           : DECLARE global-modifier-opt decl-modifier-opt ident args-opt initial-value-opt'
    p[0] = DeclareStmt(p, variable=p[4], modifiers=p[2] + p[3], size=None, parameters=p[5], initial_value=p[6])

def p_declaration2(p):
    'declaration           : DECLARE global-modifier-opt decl-modifier-opt ident array-size args-opt initial-array-opt'
    p[0] = DeclareStmt(p, variable=p[4], modifiers=p[2] + p[3], size=p[5], parameters=p[6], initial_value=p[7])

def p_family_declaration(p):
    'family-declaration    : FAMILY ident NEWLINE stmts-opt END FAMILY'
    p[0] = FamilyStmt(p, name=p[2], statements=p[4])

def p_family_declaration_error(p):
    'family-declaration    : FAMILY ident NEWLINE stmts-opt error'
    raise_parse_exception(p, "Expected 'end family'")

def p_global_modifier_opt(p):
    '''global-modifier-opt   : LOCAL
                             | GLOBAL'''
    p[0] = [p[1]]

def p_global_modifier_opt_empty(p):
    'global-modifier-opt   : empty'
    p[0] = []

def p_decl_modifier_opt(p):
    '''decl-modifier-opt     : CONST
                             | POLYPHONIC
                             | UI_LABEL
                             | UI_BUTTON
                             | UI_SWITCH
                             | UI_SLIDER
                             | UI_MENU
                             | UI_KNOB
                             | UI_TABLE
                             | UI_VALUE_EDIT
                             | UI_WAVEFORM
                             | UI_TEXT_EDIT
                             | UI_LEVEL_METER
                             | UI_FILE_SELECTOR'''
    p[0] = [p[1]]

def p_decl_modifier_opt_empty(p):
    'decl-modifier-opt     : empty'
    p[0] = []

def p_initial_value_opt(p):
    'initial-value-opt     : ASSIGN expression'
    p[0] = p[2]

def p_initial_value_opt_empty(p):
    'initial-value-opt     : empty'
    p[0] = None

def p_initial_array_opt(p):
    'initial-array-opt     : ASSIGN args'
    p[0] = p[2]

def p_initial_array_opt_raw(p):
    'initial-array-opt     : ASSIGN INIT_ARRAY'
    p[0] = RawArrayInitializer(p, p[2])

def p_initial_array_opt_empty(p):
    'initial-array-opt     : empty'
    p[0] = None

def p_array_size(p):
    'array-size            : LBRACK expression RBRACK'
    p[0] = p[2]

def p_set_ui_par_stmt(p):
    'set-ui-par-stmt       : varref RIGHTARROW ident ASSIGN expression'
    p[0] = handle_set_control_par(p[1], p[3], p[5])

def p_get_ui_par_expr(p):
    'get-ui-par-expr       : varref RIGHTARROW ident'
    p[0] = handle_get_control_par(p[1], p[3])

def p_subscripts(p):
    'subscripts            : LBRACK expression more-subscripts-opt RBRACK'
    p[0] = [p[2]] + p[3]

def p_more_subscripts_opt(p):
    'more-subscripts-opt   : COMMA expression more-subscripts-opt'
    p[0] = [p[2]] + p[3]

def p_more_subscripts_opt_empty(p):
    'more-subscripts-opt   : empty'
    p[0] = []

def p_id_subscripts_opt(p):
    'id-subscripts-opt      : id-subscripts'
    p[0] = p[1]

def p_id_subscripts_opt_empty(p):
    'id-subscripts-opt      : empty'
    p[0] = []

def p_id_subscripts(p):
    'id-subscripts          : LBRACK ident more-id-subscripts-opt RBRACK'
    p[0] = [p[2]] + p[3]

def p_more_id_subscripts_opt(p):
    'more-id-subscripts-opt : COMMA ident more-id-subscripts-opt'
    p[0] = [p[2]] + p[3]

def p_more_id_subscripts_opt_empty(p):
    'more-id-subscripts-opt : empty'
    p[0] = []

def p_basic_varref1(p):
    'basic-varref          : ident'
    p[0] = VarRef(p, identifier=p[1])

def p_basic_varref2(p):
    'basic-varref          : ident subscripts'
    p[0] = VarRef(p, identifier=p[1], subscripts=p[2])

def p_varref(p):
    'varref                : basic-varref'
    p[0] = p[1]

def p_varref_with_dot(p):
    'varref                : basic-varref DOT varref'
    p[0] = VarRef(p, ID(p, identifier='%s.%s' % (p[1].identifier, p[3].identifier)), subscripts=p[1].subscripts + p[3].subscripts)

def p_assignment(p):
    'assignment            : varref ASSIGN expression'
    p[0] = AssignStmt(p, p[1], p[3])

def p_literal_number(p):
    'literal               : NUMBER'
    p[0] = Number(p, p[1])

def p_literal_string(p):
    'literal               : STRING'
    p[0] = String(p, p[1])

def p_expression_binary(p):
    '''expression          : expression PLUS expression
                           | expression MINUS expression
                           | expression TIMES expression
                           | expression DIVIDE expression
                           | expression MOD expression
                           | expression BITWISE_AND expression
                           | expression BITWISE_OR expression
                           | expression COMPARE expression
                           | expression AND expression
                           | expression OR expression
                           | expression CONCAT expression'''
    p[0] = BinOp(p, p[1], p[2], p[3])

def p_expression_unary(p):
    '''expression          : NOT expression
                           | BITWISE_NOT expression
                           | MINUS expression %prec UMINUS'''
    p[0] = UnaryOp(p, p[1], p[2])

def p_expression_paren(p):
    'expression          : LPAREN expression RPAREN'
    p[0] = p[2]

def p_expression_other(p):
    '''expression        : literal
                         | varref
                         | function-call
                         | get-ui-par-expr'''
    p[0] = p[1]

def p_ident(p):
    'ident                 : ID'
    p[0] = ID(p, p[1])

def p_dummy(p):
    '''dummy                 : COMMENT
                             | LINECONT'''
    p[0] = 'Dummy(%s)' % p[1]

def p_empty(p):
    'empty                 :'
    p[0] = p[0]

def p_error(p):
    'error                 :'
    raise_parse_exception(p, 'Syntax error')

# grammar:
# # ---------------------------------------------------------------------------------

# g('script                : newlines-opt toplevels', lambda p: Module(p, blocks=p[2]))
# g('                      | newlines-opt error    ', RaiseParseException('syntax error'))
# g('toplevels             : toplevel toplevels', AddToList())
# g('                      | empty             ', EmptyList)
# g('''toplevel            : callback newlines-opt
#                          | functiondef newlines-opt
#                          | import newlines-opt''', ReturnParam())

# g('newlines-opt          : newlines-opt NEWLINE | empty', ReturnNone)

# g('callback              : BEGIN_CALLBACK NEWLINE stmts-opt END_CALLBACK', lambda p: Callback(p, p[1]['name'], p[3], p[1]['ui_control']))

# g('import                : IMPORT STRING         ', lambda p: Import(p, p[2]))
# g('                      | IMPORT STRING AS ident', lambda p: Import(p, p[2], p[4]))

# g('functiondef           : FUNCTION ident params-opt          return-value-opt override-opt NEWLINE stmts-opt END FUNCTION', lambda p: FunctionDef(p, p[2], p[3], p[4], p[7], override=p[5]))
# g('                      | TASKFUNC ident taskfunc-params-opt return-value-opt override-opt NEWLINE stmts-opt END TASKFUNC', lambda p: FunctionDef(p, p[2], p[3], p[4], p[7], override=p[5], is_taskfunc=True))
# g('return-value-opt      : RIGHTARROW ident', ReturnParam(i=2))
# g('                      | empty', ReturnNone)
# g('override-opt          : OVERRIDE', lambda p: True)
# g('                      | empty   ', lambda p: False)

# g('stmts-opt             : stmts', ReturnParam())
# g('                      | empty', EmptyList)  # changed

# g('stmts                 : stmt      ', AddToEmptyList(dont_add_none=True))
# g('                      | stmt stmts', AddToList(dont_add_none=True))

# g('''stmt                : declaration NEWLINE
#                          | propertydef NEWLINE
#                          | family-declaration NEWLINE
#                          | assignment NEWLINE
#                          | preprocessor-stmt NEWLINE
#                          | procedure-call NEWLINE
#                          | if-stmt NEWLINE
#                          | while-stmt NEWLINE
#                          | for-stmt NEWLINE
#                          | select-stmt NEWLINE
#                          | set-ui-par-stmt NEWLINE''', ReturnParam())
# g('                      | NEWLINE | dummy      ', ReturnNone)
# #g('                      | error                ', RaiseParseException())

# g('preprocessor-stmt     : SET_CONDITION LPAREN ID RPAREN',   lambda p: PreprocessorCondition(p, p[1], p[3]))
# g('                      | RESET_CONDITION LPAREN ID RPAREN', lambda p: PreprocessorCondition(p, p[1], p[3]))

# g('if-stmt               : IF expression NEWLINE stmts-opt else-if-opt END IF', lambda p: IfStmt(p, condition_stmts_tuples = [(p[2], p[4])] + p[5]))
# g('                      | IF expression NEWLINE stmts-opt else-if-opt error ', RaiseParseException("Expected 'end if'"))
# g('else-if-opt           : ELSE else-if-condition-opt NEWLINE stmts-opt else-if-opt', lambda p: [(p[2], p[4])] + p[5]) # [(condition, stmts), ...]
# g('                      | empty                                                        ', EmptyList)
# g('else-if-condition-opt : IF expression', ReturnParam(2))
# g('                      | empty        ', ReturnNone)  # condition is None for else statements (not else if)

# g('while-stmt            : WHILE expression NEWLINE stmts-opt END WHILE', lambda p: WhileStmt(p, p[2], p[4]))
# g('                      | WHILE expression NEWLINE stmts-opt error    ', RaiseParseException("Expected 'end while'"))
# g('for-stmt              : FOR varref ASSIGN expression updownto expression NEWLINE stmts-opt END FOR', lambda p: ForStmt(p, p[2], p[4], p[6], p[8], downto=p[5]))
# g('                      | FOR varref ASSIGN expression updownto expression STEP expression NEWLINE stmts-opt END FOR', lambda p: ForStmt(p, p[2], p[4], p[6], p[10], downto=p[5], step=p[8]))
# g('                      | FOR varref ASSIGN expression updownto expression NEWLINE stmts-opt error  ', RaiseParseException("Expected 'end for'"))
# g('updownto              : TO | DOWNTO', lambda p: p[1] == 'downto') # True if 'downto', False if 'to'

# g('select-stmt           : SELECT expression NEWLINE select-cases END SELECT', lambda p: SelectStmt(p, p[2], p[4]))
# g('                      | SELECT expression NEWLINE select-cases error     ', RaiseParseException("Expected 'end select'"))
# g('select-cases          : select-case select-cases', AddToList())
# g('                      | empty                   ', EmptyList)
# g('select-case           : newlines-opt CASE expression NEWLINE stmts-opt              ', lambda p: ((p[3], None), p[5])) # ((range_start, range_end), stmts)
# g('                      | newlines-opt CASE expression TO expression NEWLINE stmts-opt', lambda p: ((p[3], p[5]), p[7])) # ((range_start, range_end), stmts)
# g('select-case           : newlines-opt ELSE NEWLINE stmts-opt                         ', lambda p: ((Number(p, 0x80000000), Number(p, 0x7FFFFFFF)), p[4])) # ((range_start, range_end), stmts), min_int to max_int

# g('params-opt            : params', ReturnParam())
# g('                      | empty ', EmptyList)
# g('params                : LPAREN ID more-params-opt RPAREN', AddToList(2, 3))
# g('                      | LPAREN RPAREN', EmptyList)
# g('                      | INIT_ARRAY', lambda p: InitArrayToList(p, p[1]))
# g('more-params-opt       : COMMA ID more-params-opt', AddToList(2, 3))
# g('                      | empty                   ', EmptyList)

# g('taskfunc-params-opt   : taskfunc-params', ReturnParam())
# g('                      | empty     ', EmptyList)
# g('taskfunc-params       : LPAREN    ID more-taskfunc-params-opt RPAREN', lambda p: [(None, p[2])] + p[3])
# g('                      | LPAREN ID ID more-taskfunc-params-opt RPAREN', lambda p: [(p[2], p[3])] + p[4])
# g('                      | LPAREN RPAREN                                ', EmptyList)
# g('more-taskfunc-params-opt : COMMA    ID more-taskfunc-params-opt', lambda p: [(None, p[2])] + p[3])
# g('                         | COMMA ID ID more-taskfunc-params-opt', lambda p: [(p[2], p[3])] + p[4])
# g('                         | empty                               ', EmptyList)

# g('args-opt              : args', ReturnParam())
# g('                      | empty ', EmptyList)
# g('args                  : LPAREN expression more-args-opt RPAREN', AddToList(2, 3))
# g('                      | INIT_ARRAY', lambda p: InitArrayToList(p, p[1]))
# g('                      | LPAREN RPAREN', EmptyList)
# g('more-args-opt         : COMMA expression more-args-opt', AddToList(2, 3))
# g('                      | empty                         ', EmptyList)

# g('function-call         : ident args    ', lambda p: FunctionCall(p, function_name=p[1], parameters=p[2]))
# g('                      | CALL ident args-opt', lambda p: FunctionCall(p, function_name=p[2], parameters=p[3], is_procedure=False, using_call_keyword=True))
# g('procedure-call        : ident args-opt', lambda p: FunctionCall(p, function_name=p[1], parameters=p[2], is_procedure=True))
# g('                      | CALL ident args-opt', lambda p: FunctionCall(p, function_name=p[2], parameters=p[3], is_procedure=True, using_call_keyword=True))

# g('propertydef           : PROPERTY ident NEWLINE newlines-opt functiondefs END PROPERTY', lambda p: PropertyDef(p, p[2], functions=p[5]))
# g('                      | PROPERTY ident id-subscripts-opt RIGHTARROW varref',               lambda p: PropertyDef(p, p[2], indices=p[3], alias_varref=p[5]))
# g('functiondefs          : functiondef newlines-opt',              AddToEmptyList(item_index = 1, dont_add_none=True))
# g('                      | functiondef newlines-opt functiondefs', AddToList(item_index = 1, list_index = 3, dont_add_none=True))

# g('declaration           : DECLARE global-modifier-opt decl-modifier-opt ident args-opt initial-value-opt', lambda p: DeclareStmt(p, variable=p[4], modifiers=p[2] + p[3], size=None, parameters=p[5], initial_value=p[6]))
# g('                      | DECLARE global-modifier-opt decl-modifier-opt ident array-size args-opt initial-array-opt', lambda p: DeclareStmt(p, variable=p[4], modifiers=p[2] + p[3], size=p[5], parameters=p[6], initial_value=p[7]))
# g('family-declaration    : FAMILY ident NEWLINE stmts-opt END FAMILY', lambda p: FamilyStmt(p, name=p[2], statements=p[4]))
# g('                      | FAMILY ident NEWLINE stmts-opt error     ', RaiseParseException("Expected 'end family'"))
# g('global-modifier-opt   : LOCAL | GLOBAL', AddToEmptyList())
# g('                      | empty         ', EmptyList)
# g('decl-modifier-opt     : CONST | POLYPHONIC | UI_LABEL | UI_BUTTON | UI_SWITCH | UI_SLIDER | UI_MENU | UI_KNOB | UI_TABLE | UI_VALUE_EDIT | UI_WAVEFORM | UI_TEXT_EDIT | UI_LEVEL_METER | UI_FILE_SELECTOR | ', AddToEmptyList())
# g('                      | empty             ', EmptyList)
# g('initial-value-opt     : ASSIGN expression     ', ReturnParam(2))
# g('                      | empty                 ', ReturnNone)
# g('initial-array-opt     : ASSIGN args           ', ReturnParam(2))
# g('                      | ASSIGN INIT_ARRAY     ', lambda p: RawArrayInitializer(p, p[2]))
# g('                      | empty                 ', ReturnNone)
# g('array-size            : LBRACK expression RBRACK', ReturnParam(2))

# g('set-ui-par-stmt       : varref RIGHTARROW ident ASSIGN expression',   lambda p: handle_set_control_par(p[1], p[3], p[5]))
# g('get-ui-par-expr       : varref RIGHTARROW ident',                     lambda p: handle_get_control_par(p[1], p[3]))

# #g('basic-varref          : ident                      ', ReturnParam())
# #g('                      | basic-varref DOT ident     ', lambda p: '%s.%s' % (p[1], p[3]))

# g('subscripts            : LBRACK expression more-subscripts-opt RBRACK', AddToList(2, 3))
# g('more-subscripts-opt   : COMMA expression more-subscripts-opt        ', AddToList(2, 3))
# g('                      | empty                                       ', EmptyList)

# g('id-subscripts-opt      : id-subscripts', ReturnParam(1))
# g('id-subscripts-opt      : empty',         EmptyList)
# g('id-subscripts          : LBRACK ident more-id-subscripts-opt RBRACK', AddToList(2, 3))
# g('more-id-subscripts-opt : COMMA ident more-id-subscripts-opt        ', AddToList(2, 3))
# g('                       | empty                                     ', EmptyList)

# g('basic-varref          : ident                         ', lambda p: VarRef(p, identifier=p[1]))
# g('                      | ident subscripts              ', lambda p: VarRef(p, identifier=p[1], subscripts=p[2]))
# g('varref                : basic-varref                  ', lambda p: p[1])
# g('                      | basic-varref DOT varref       ', lambda p: VarRef(p, ID(p, identifier='%s.%s' % (p[1].identifier, p[3].identifier)),
#                                                                                 subscripts=p[1].subscripts + p[3].subscripts))

# g('assignment            : varref ASSIGN expression', lambda p: AssignStmt(p, p[1], p[3]))

# g('literal               : NUMBER', lambda p: Number(p, p[1]))
# g('                      | STRING', lambda p: String(p, p[1]))

# g('''expression          : expression PLUS expression
#                          | expression MINUS expression
#                          | expression TIMES expression
#                          | expression DIVIDE expression
#                          | expression MOD expression
#                          | expression BITWISE_AND expression
#                          | expression BITWISE_OR expression
#                          | expression COMPARE expression
#                          | expression AND expression
#                          | expression OR expression
#                          | expression CONCAT expression ''', lambda p: BinOp(p, p[1], p[2], p[3]))
# g('''                    | NOT expression
#                          | BITWISE_NOT expression
#                          | MINUS expression %prec UMINUS''', lambda p: UnaryOp(p, p[1], p[2]))
# g('''                    | LPAREN expression RPAREN     ''', ReturnParam(2))
# g('''                    | literal
#                          | varref
#                          | function-call
#                          | get-ui-par-expr              ''',ReturnParam(1))

# g('ident                 : ID', lambda p: ID(p, p[1]))

# g('dummy                 : COMMENT | LINECONT', lambda p: 'Dummy(%s)' % p[1])
# g('empty                 :                   ', ReturnParam(0))
# g('error                 :                   ', RaiseParseException())

def init(outputdir=None):
    outputdir = outputdir or os.path.dirname(__file__)  # os.getcwd()
    current_module = sys.modules[__name__]
    #print (outputdir, current_module)
    debug = 0
    optimize = 0
    lex.lex(optimize=0, debug=debug)
    return yacc.yacc(method="LALR", optimize=optimize, debug=debug,
                     write_tables=0, module=current_module, start='script',
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
