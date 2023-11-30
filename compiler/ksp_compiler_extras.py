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

from ksp_ast import *
from ksp_ast_processing import ASTVisitor, ASTModifier, flatten
import ksp_builtins
import re
import math

symbol_table = {}
nckp_table = []
user_defined_functions = {}
key_ids = {}

pgs_functions = set(['_pgs_create_key', '_pgs_key_exists', '_pgs_set_key_val', '_pgs_get_key_val',
                     'pgs_create_key',  'pgs_key_exists',  'pgs_set_key_val', 'pgs_get_key_val',
                     'pgs_create_str_key', 'pgs_str_key_exists', 'pgs_set_str_key_val', 'pgs_get_str_key_val'])

mark_constant_re = re.compile(r'MARK_([1-9]|1[0-9]|2[0-8])')

def clear_symbol_table():
    symbol_table.clear()
    key_ids.clear()
    user_defined_functions.clear()

def add_nckp_var_to_nckp_table(nckp_ui_variable):
        nckp_table.append(nckp_ui_variable.lower())

class ValueUndefinedException(ParseException):
    def __init__(self, node, msg='Value of variable is undefined'):
        ParseException.__init__(self, node, msg)

class Variable:
    '''Class for variables (used in symbol table)'''

    def __init__(self, name, size = 1, params = None, control_type = None, is_constant = False, is_polyphonic = False, value = None):
        self.name = name
        self.size = size
        self.params = params or []
        self.control_type = control_type
        self.is_constant = is_constant
        self.is_polyphonic = is_polyphonic
        self.value = value

def move_on_init_first(module):
    on_init_blocks = [b for b in module.blocks if isinstance(b, Callback) and b.name == 'init']

    if on_init_blocks:
        on_init = on_init_blocks[0]
        module.blocks.remove(on_init)
        module.blocks.insert(0, on_init)

def toint(i, bits=32):
    ' converts to a signed integer with bits bits '
    i &= (1 << bits) - 1       # get last "bits" bits, as unsigned

    if i & (1 << (bits - 1)):  # is negative in N-bit 2's comp
        i -= 1 << bits         # ... so make it negative

    return int(i)

def sign(x):
    if x < 0:
        return -1
    elif x > 0:
        return 1
    else:
        return 0

def assert_numeric(x):
    if type(x) not in (int, Decimal):
        raise ValueUndefinedException(x, 'Numeric value expected!')

def normalize_numeric(x):
    # constrain integers to the range of a 32-bit signed int
    if type(x) is int:
        return toint(x)
    # ... and leave real numbers as they are
    else:
        return x

def evaluate_expression(expr):
    if isinstance(expr, BinOp):
        a, b = evaluate_expression(expr.left), evaluate_expression(expr.right)
        op = expr.op

        if op in ['+', '-', '*', '/', '<', '<=', '>', '>=', '=', '#']:
            assert_numeric(a)
            assert_numeric(b)

            if op == '+':
                return normalize_numeric(a + b)
            elif op == '-':
                return normalize_numeric(a - b)
            elif op == '*':
                return normalize_numeric(a * b)
            elif op == '/':
                if b == 0:
                    return normalize_numeric(b)
                else:
                    if type(a) is int and type(b) is int:
                        # division with truncation
                        # a // b yields the wrong result in case of negative numbers, eg. -10/9
                        return int(math.copysign(abs(a) // abs(b), a / b))
                    else:
                        return a / b
            elif op == '=':
                return a == b
            elif op == '<':
                return a < b
            elif op == '<=':
                return a <= b
            elif op == '>':
                return a > b
            elif op == '>=':
                return a >= b
            elif op == '#':
                return a != b
        elif op in ['.and.', '.or.', '.xor.']:
            a, b = toint(a), toint(b)

            if op == '.and.':
                return a & b
            elif op == '.or.':
                return a | b
            else:
                return a ^ b
        elif op == 'mod':
            # we don't have to check if b is int type, since we already check for type mismatches in visitBinOp function
            if type(a) is int:
                a, b = toint(a), toint(b)
                result = abs(a) % abs(b)

                if a < 0:
                    return -result
                else:
                    return result
            elif type(a) is Decimal:
                return Decimal(math.fmod(a, b))
        elif op == '&':
            return str(a) + str(b)
        elif op in ['and', 'xor', 'or']:
            a, b = bool(a), bool(b)

            if op == 'and':
                return a and b
            elif op == 'or':
                return a or b
            else:
                return a ^ b
    elif isinstance(expr, UnaryOp):
        a = evaluate_expression(expr.right)

        if expr.op == '-':
            return normalize_numeric(-a)
        elif expr.op == '.not.':
            return toint(0xFFFFFFFF ^ a)
    elif isinstance(expr, Integer) or isinstance(expr, String) or isinstance(expr, Boolean) or isinstance(expr, Real):
        return expr.value
    elif isinstance(expr, VarRef):
        name = str(expr.identifier)

        if name in ksp_builtins.constants:
            return name

        if name in ksp_builtins.variables:
            raise ParseException(expr, 'Built-in variables cannot be used in this context!')

        if name.lower() not in symbol_table:
            raise ParseException(expr, 'Variable not declared: %s!' % name)

        value = symbol_table[name.lower()].value

        if value is None:
            raise ValueUndefinedException(expr)

        if len(expr.subscripts) > 1:
            raise ParseException(expr, 'More than one subscript found: %s!' % str(expr))

        if expr.subscripts:
            subscript = int(evaluate_expression(expr.subscripts[0]))
        else:
            subscript = None

        if (expr.identifier.prefix in '%!?') != (subscript is not None):
            raise ParseException(expr, 'Use of subscript is invalid!')

        if subscript:
            if 0 <= subscript < len(value):
                return value[subscript]
            else:
                # WARNING: index out of bounds
                return 0
        else:
            return value
    elif isinstance(expr, FunctionCall):
        name = str(expr.function_name)
        parameters = [evaluate_expression(param) for param in expr.parameters]
        funcs2numparameters = {
            'abs': 1,
            'in_range': 3,
            'sh_left': 2,
            'sh_right': 2,
            'by_marks': 1,
            'int_to_real': 1,
            'real_to_int': 1,
            'int': 1,
            'real': 1
            }

        if name in list(funcs2numparameters.keys()):
            if len(parameters) != funcs2numparameters[name]:
                raise ParseException(expr, 'Wrong number of parameters for %s()!' % name)

            if name == 'abs':
                return abs(parameters[0])
            elif name == 'in_range':
                return parameters[1] <= parameters[0] <= parameters[2]
            elif name == 'sh_left':
                return toint(parameters[0] << (parameters[1] % 32))
            elif name == 'sh_right':
                return toint(parameters[0] >> (parameters[1] % 32))
            elif name == 'by_marks':   # TODO: check if this can be removed
                return toint(parameters[0] | 0x80000000)
            elif name in ['int_to_real', 'real']:
                return Decimal(toint(parameters[0]))
            elif name in ['real_to_int', 'int']:
                return toint(int(parameters[0]))

        raise ValueUndefinedException(expr, 'Constant value expected!')

def assert_type(node, test_type):
    ''' Verify that <node> has a type that matches (is compatible with) <type> '''
    if node is None:
        node_type = 'None'
        raise Exception()

    node_type = node.type

    if node_type != test_type and not (node_type in ('integer', 'real') and test_type == 'numeric'):
        raise ParseException(node, 'Expected expression of %s type, got %s type instead!' % (test_type, node_type))

def highest_precision(type1, type2):
    if type1 == 'real' or type2 == 'real':
        return 'real'
    else:
        return 'integer'

class ASTVisitorDetermineExpressionTypes(ASTVisitor):
    def __init__(self, ast, functions):
        ASTVisitor.__init__(self)
        self.functions = functions
        self.traverse(ast)

    def visitFunctionCall(self, parent, node, *args):
        self.visit_children(parent, node, *args)
        function_name = node.function_name.identifier

        if function_name in ksp_builtins.function_signatures or   \
           (function_name in ksp_builtins.function_signatures and \
            function_name in self.functions and self.functions[function_name].override):

            matches_param_count = False

            for s in ksp_builtins.function_signatures[function_name]:
                params, return_type = s

                if type:
                    node.type = return_type
                else:
                    node.type = 'undefined'

                passed_params = node.parameters

                if len(passed_params) == len(params) and matches_param_count == False:
                    matches_param_count = True

                for (param_descriptor, passed_param) in zip(params, passed_params):
                    param_descriptor = param_descriptor.replace('<', '').replace('>', '')
                    is_text = 'text' in param_descriptor or param_descriptor.endswith('name') or param_descriptor.endswith('path')

                    if not is_text:
                        # special case: the abs function returns an integer or real depending on what param type it's given
                        if function_name == 'abs' and passed_param.type in ('integer', 'real'):
                            node.type = passed_param.type
                        elif 'any-array-variable' in param_descriptor:
                            if not passed_param.type in ('integer array', 'real array', 'string array'):
                                assert_type(passed_param, 'integer, real or string array')
                        elif 'int-or-string-array' in param_descriptor:
                            if not passed_param.type in ('integer array', 'string array'):
                                assert_type(passed_param, 'integer or string array')
                        elif 'int-or-real-array' in param_descriptor:
                            if not passed_param.type in ('integer array', 'real array'):
                                assert_type(passed_param, 'integer or real array')
                        elif 'string-array' in param_descriptor:
                            assert_type(passed_param, 'string array')
                        elif 'int-array' in param_descriptor:
                            assert_type(passed_param, 'integer array')
                        elif 'real-array' in param_descriptor:
                            assert_type(passed_param, 'real array')
                        elif 'key-id' in param_descriptor:
                            if not isinstance(passed_param, VarRef):
                                raise ParseException(node, 'Expected PGS key ID!')

                            passed_param.type = 'key-id'
                        elif 'int-or-real-value' in param_descriptor:
                            assert_type(passed_param, 'numeric')
                        elif 'real-value' in param_descriptor:
                            assert_type(passed_param, 'real')
                        elif 'value' in param_descriptor:
                            assert_type(passed_param, 'integer')
                        elif not 'variable' in param_descriptor:
                            assert_type(passed_param, 'integer')

            if matches_param_count == False:
                if len(ksp_builtins.function_signatures[function_name]) > 1:
                    raise ParseException(node, \
                        'Wrong number of parameters for %s()! This function has multiple overloads, neither of which expect %d parameter%s given!' \
                        % (function_name, len(passed_params), 's that were' if len(passed_params) > 1 else ' that was' ))
                else:
                    raise ParseException(node, 'Wrong number of parameters for %s(): expected %d, got %d!' % (function_name, len(params), len(passed_params)))

        return False

    def visitBinOp(self, parent, expr, *args):
        self.visit_children(parent, expr, *args)

        if expr.op == '&':
            expr.type = 'string'
        elif expr.op in ('+', '-', '*', '/', 'mod'):
            assert_type(expr.left, 'numeric')
            assert_type(expr.right, 'numeric')
            expr.type = highest_precision(expr.left.type, expr.right.type)
        elif expr.op in ('.and.', '.or.', '.xor.'):
            assert_type(expr.left, 'integer')
            assert_type(expr.right, 'integer')
            expr.type = 'integer'
        elif expr.op in '< <= > >= = #':
            assert_type(expr.left, 'numeric')
            assert_type(expr.right, 'numeric')
            expr.type = 'boolean'
        elif expr.op in 'and or xor':
            assert_type(expr.left, 'boolean')
            assert_type(expr.right, 'boolean')
            expr.type = 'boolean'
        else:
            raise Exception()

        if expr.op in '+ - * / < <= > >= = # mod' and expr.left.type != expr.right.type:
            raise ParseException(expr,                                                                                                                 \
                                 'Operands are of different types: %s and %s! Please use int(...) or real(...) functions to explicitly cast the type.' \
                                 % (expr.left.type, expr.right.type))

        return False

    def visitUnaryOp(self, parent, expr, *args):
        self.visit_children(parent, expr, *args)

        if expr.op == '-':
            assert_type(expr.right, 'numeric')
            expr.type = expr.right.type
        elif expr.op == '.not.':
            assert_type(expr.right, 'integer')
            expr.type = 'integer'
        elif expr.op == 'not':
            assert_type(expr.right, 'boolean')
            expr.type = 'boolean'

        return False

    def visitInteger(self, parent, expr, *args):
        expr.type = 'integer'

    def visitReal(self, parent, expr, *args):
        expr.type = 'real'

    def visitString(self, parent, expr, *args):
        expr.type = 'string'

    def visitRawArrayInitializer(self, parent, expr, *args):
        expr.type = 'integer array'

    def visitID(self, parent, expr, *args):
        if expr.prefix:
            expr.type = {'$': 'integer',
                         '%': 'integer array',
                         '@': 'string',
                         '!': 'string array',
                         '?': 'real array',
                         '~': 'real'}[expr.prefix]
        else:
            expr.type = 'integer' # function return value

    def visitVarRef(self, parent, expr, *args):
        self.visit_children(parent, expr, *args)

        if expr.subscripts:
            assert_type(expr.subscripts[0], 'integer')

            if not expr.identifier.type.endswith(' array'):
                raise ParseException(expr.identifier, 'Expected array!')

            # an added subscript turns e.g. an integer array into just an integer
            expr.type = expr.identifier.type.replace(' array', '')
        else:
            expr.type = expr.identifier.type

        return False

class ASTVisitorCheckStatementExprTypes(ASTVisitor):
    def __init__(self, ast):
        ASTVisitor.__init__(self, visit_expressions = False)
        self.traverse(ast)

    def visitDeclareStmt(self, parent, node, *args):
        if node.initial_value and not (type(node.initial_value) is list):
            assert_type(node.initial_value, node.variable.type)

        if node.size:
            assert_type(node.size, 'integer')

    def visitAssignStmt(self, parent, node, *args):
        # assigning an integer to a string variable is ok, so don't treat that as an error
        try:
            if not (node.expression and node.expression.type in ('integer', 'real') and node.varref.type == 'string'):
                assert_type(node.expression, node.varref.type)
        except ParseException as e:
            raise ParseException(node.varref, e.msg)

    def visitWhileStmt(self, parent, node, *args):
        assert_type(node.condition, 'boolean')

    def visitForStmt(self, parent, node, *args):
        assert_type(node.loopvar, 'numeric')
        assert_type(node.start, 'numeric')
        assert_type(node.end, 'numeric')

        if node.step:
            assert_type(node.step, 'numeric')

    def visitIfStmt(self, parent, node, *args):
        for (condition, stmts) in node.condition_stmts_tuples:
            if condition:
                assert_type(condition, 'boolean')

    def visitSelectStmt(self, parent, node, *args):
        for ((start, stop), stmts) in node.range_stmts_tuples:
            assert_type(start, 'integer')

            if stop:
                assert_type(stop, 'integer')

class ASTVisitorFindUsedVariables(ASTVisitor):
    '''Find used variables by traversing AST and store in set, used_variables'''

    def __init__(self, ast, used_variables_set):
        ASTVisitor.__init__(self)
        self.used_variables = used_variables_set
        self.traverse(ast)

    def visitDeclareStmt(self, parent, node, *args):
        # visit all children except the first one (the declared variable)
        for child in node.get_childnodes()[1:]:
            self.dispatch(node, child, *args)

        return False

    def visitID(self, parent, node, *args):
        self.used_variables.add(str(node).lower())
        return False

class ASTVisitorFindUsedFunctions(ASTVisitor):
    '''Find used functions by traversing AST and store in dictionary, call_graph'''

    def __init__(self, ast, used_functions):
        ASTVisitor.__init__(self, visit_expressions = False)
        self.call_graph = {}
        self.traverse(ast)

        self.mark_used_functions_using_depth_first_traversal(self.call_graph, visited = used_functions)

    def visitFunctionDef(self, parent, node):
        self.visit_children(parent, node, node.name.identifier)
        return False

    def visitCallback(self, parent, node):
        self.visit_children(parent, node, None)
        return False

    def visitFunctionCall(self, parent, node, top_level):
        target = node.function_name.identifier

        if node.using_call_keyword:
            source = top_level

            if not source in self.call_graph:
                self.call_graph[source] = []

            if not target in self.call_graph:
                self.call_graph[target] = []

            self.call_graph[source].append(target)

        return False

    def mark_used_functions_using_depth_first_traversal(self, call_graph, start_node = None, visited = None):
        ''' Make a depth-first traversal of call graph and set the used attribute of functions invoked directly or indirectly from some callback.
            The graph is represented by a dictionary where graph[f1] == f1 means that the function with name f1 calls the function with name f2 (the names are strings).'''
        if visited is None:
            visited = set()

        nodes_to_visit = set()

        if start_node is None:
            nodes_to_visit = set(call_graph.get(None, []))  # None represents the source of a normal callback (a callback invoking a function as opposed to a function invoking a function)
        else:
            if start_node not in visited:
                visited.add(start_node)
                nodes_to_visit = set([x for x in call_graph[start_node] if x is not None])

        for n in nodes_to_visit:
            self.mark_used_functions_using_depth_first_traversal(call_graph, n, visited)

class ASTVisitorCheckDeclarations(ASTVisitor):
    def __init__(self, ast):
        ASTVisitor.__init__(self)
        self.traverse(ast)

    def assert_true(self, condition, node, msg):
        if not condition:
            raise ParseException(node, msg)

    def visitFunctionCall(self, parent, node, *args):
        function_name = node.function_name.identifier

        if function_name in pgs_functions:
            # visit all children except the first one (the key-id)
            for child in node.get_childnodes()[1:]:
                self.dispatch(node, child, *args)

            return False

    def visitFunctionDef(self, parent, node, *args):
        if node.name.identifier in user_defined_functions:
            raise ParseException(node, 'A variable or a function with the same name already exists!')

        user_defined_functions[node.name.identifier] = node

        return True

    def visitDeclareStmt(self, parent, node, *args):
        name = str(node.variable)
        is_ui_control = [x for x in node.modifiers if x.startswith('ui_')]

        if is_ui_control:
            self.assert_true(not 'const' in node.modifiers,      node, 'UI controls cannot be constant!')
            self.assert_true(not 'polyphonic' in node.modifiers, node, 'UI controls cannot be polyphonic!')

        for ui_control_type, params in ksp_builtins.ui_control_signatures.items():
            if ui_control_type in node.modifiers:
                par_count = len(node.parameters)

                if len(params) == 0:
                    self.assert_true(not node.parameters, node, 'This UI control type does not have any parameters!')
                else:
                    self.assert_true(node.parameters and par_count == len(params), node,
                                     "Expected %d parameters (%d %s given): %s" % (len(params),
                                                                                  par_count,
                                                                                  'was' if par_count < 2 else 'were',
                                                                                  ', '.join(params).replace('-', ' ')))

        if name.lower() in symbol_table:
            raise ParseException(node.variable, 'Redeclaration of %s!' % name)

        if node.size:
            try:
                size = evaluate_expression(node.size)
            except ValueUndefinedException:
                raise ParseException(node.size, 'Array size is not a constant or uses undefined variables!')
        else:
            size = 1

        initial_value = None

        if 'const' in node.modifiers:
            if node.initial_value is None:
                raise ParseException(node.variable, 'A constant must have a value assigned!')

            init_expr = node.initial_value

            # First need to check if the initial value is an NI constant
            if not (isinstance(init_expr, VarRef) and (str(init_expr.identifier).upper() in ksp_builtins.all_builtins)                     \
               or ("function_name" in init_expr.__dict__  and str(init_expr.function_name) in ksp_builtins.functions_with_constant_return) \
               and str(init_expr.function_name) not in ksp_builtins.functions_evaluated_with_optimize_code):

                try:
                    test = evaluate_expression(node.initial_value)
                    if test == None:
                        raise ParseException(node.variable, 'A constant can have only one value assigned, it cannot be an array!')
                    else:
                        initial_value = test
                except ValueUndefinedException:
                    raise ParseException(node.initial_value, 'Expression uses non-constant values or undefined constant variables!')
        try:
            params = []

            for param in node.parameters:
                # VALUE_EDIT_MODE_NOTE_NAMES is used in declare statements, but don't force a known value to evaluate to when it's used as a param
                if True or isinstance(param, VarRef) \
                   and (param.identifier.prefix + param.identifier.identifier in ['VALUE_EDIT_MODE_NOTE_NAMES', '$VALUE_EDIT_MODE_NOTE_NAMES']
                   or param.identifier.prefix + param.identifier.identifier in ksp_builtins.all_builtins):

                    params.append(param)
                else:
                    params.append(evaluate_expression(param))
        except ValueUndefinedException:
            raise ParseException(node, 'Expression uses non-constant values or undefined constant variables!')

        if is_ui_control:
            control_type = is_ui_control[0]
        else:
            control_type = None

        if type(parent) == Callback and parent.name != 'init':
            raise ParseException(node, 'Variables may only be declared inside the "on init" callback!')

        is_constant = ('const' in node.modifiers and initial_value is not None)
        is_polyphonic = 'polyphonic' in node.modifiers

        symbol_table[name.lower()] = Variable(node.variable, size, params, control_type, is_constant, is_polyphonic, initial_value)

        self.visit_children(parent, node, *args)

        return False

    def visitID(self, parent, node, *args):
        name = str(node)
        special_names = ['NO_SYS_SCRIPT_RLS_TRIG', 'NO_SYS_SCRIPT_PEDAL', 'NO_SYS_SCRIPT_GROUP_START', 'NO_SYS_SCRIPT_ALL_NOTES_OFF']

        if not name in ksp_builtins.all_builtins and not name in ksp_builtins.functions \
           and not name in user_defined_functions and not name in special_names         \
           and not name.lower() in symbol_table and not name.lower() in nckp_table:

            raise ParseException(node, 'Undeclared variable or function: %s!' % name)

class ASTModifierSimplifyExpressions(ASTModifier):
    def __init__(self, module_ast, replace_constants = True):
        ASTModifier.__init__(self)
        self.replace_constants = replace_constants
        self.traverse(module_ast)

    def evaluate_expression_or_same(self, expr):
        if expr is None:
            return None
        try:
            result = evaluate_expression(expr)

            if type(result) is int and not isinstance(expr, Integer):
                return Integer(expr.lexinfo, result)
            if type(result) is Decimal and not isinstance(expr, Real):
                return Real(expr.lexinfo, result)
            if type(result) is bool and not isinstance(expr, Boolean):
                return Boolean(expr.lexinfo, result)
        except SyntaxError:
            pass

        return expr

    def modifyDeclareStmt(self, node):
        ASTModifier.modifyDeclareStmt(self, node)
        return [node]

    def modifyBinOp(self, node):
        node = ASTModifier.modifyBinOp(self, node)
        node.left = self.evaluate_expression_or_same(node.left)
        node.right = self.evaluate_expression_or_same(node.right)

        if node.op == '*':
            if isinstance(node.left, (Integer, Real)):
                if node.left.value == 0:
                    return node.left
                elif node.left.value == 1:
                    return node.right
            if isinstance(node.right, (Integer, Real)):
                if node.right.value == 0:
                    return node.right
                elif node.right.value == 1:
                    return node.left
        if node.op == '+':
            if isinstance(node.left, (Integer, Real)):
                if node.left.value == 0:
                    return node.right
            if isinstance(node.right, (Integer, Real)):
                if node.right.value == 0:
                    return node.left
        if node.op == 'or':
            if isinstance(node.left, Boolean):
                if node.left.value:
                    return node.left
                else:
                    return node.right
            elif isinstance(node.right, Boolean):
                if node.right.value:
                    return node.right
                else:
                    return node.left
        elif node.op == 'and':
            if isinstance(node.left, Boolean):
                if node.left.value:
                    return node.right
                else:
                    return node.left
            elif isinstance(node.right, Boolean):
                if node.right.value:
                    return node.left
                else:
                    return node.right

        return self.evaluate_expression_or_same(node)

    def modifyUnaryOp(self, node):
        node = ASTModifier.modifyUnaryOp(self, node)
        node.right = self.evaluate_expression_or_same(node.right)
        return self.evaluate_expression_or_same(node)

    def modifyVarRef(self, node):
        node = ASTModifier.modifyVarRef(self, node)

        # MARK_%d constants are included in the symbol table in order to be possible to use on declaration lines, don't replace them with their values
        if self.replace_constants and not mark_constant_re.match(node.identifier.identifier):
            return self.evaluate_expression_or_same(node)
        else:
            return node

    def modifyExpr(self, node):
        if isinstance(node, BinOp):
            node.left = self.evaluate_expression_or_same(node.left)
            node.right = self.evaluate_expression_or_same(node.right)
        elif isinstance(node, UnOp):
            node.right = self.evaluate_expression_or_same(node.right)

        return self.evaluate_expression_or_same(node)

    def modifyIfStmt(self, node, *args, **kwargs):
        # don't simplify the condition of "if 1=1" statements
        temp = []

        for i, (condition, stmts) in enumerate(node.condition_stmts_tuples):
            if (isinstance(condition, BinOp) and
                isinstance(condition.left, Integer) and
                isinstance(condition.right, Integer) and
                i == 0 and condition.left.value == 1 and condition.right.value == 1):

                pass
            else:
                condition = self.modify(condition, *args, **kwargs)

            stmts = flatten([self.modify(s, *args, **kwargs) for s in stmts])
            temp.append((condition, stmts))

        if not temp:
            return []
        else:
            node.condition_stmts_tuples = temp
            return [node]

class ASTModifierRemoveUnusedBranches(ASTModifier):
    '''Remove unused branches (such as if, select, while). Used if optimize mode is selected'''

    def __init__(self, module_ast):
        ASTModifier.__init__(self)
        self.traverse(module_ast)

    def is1equals1(self, node):
        return isinstance(node, BinOp) and isinstance(node.left, Integer) and isinstance(node.right, Integer) and node.left.value == 1 and node.right.value == 1

    def modifyIfStmt(self, node):
        statements = ASTModifier.modifyIfStmt(self, node)

        if len(statements) == 1:
            node = statements[0]
            condition_stmts_tuples = []

            for (i, (condition, stmts)) in enumerate(node.condition_stmts_tuples):
                try:
                    value = None

                    if condition:
                        value = evaluate_expression(condition)
                except ParseException:
                    pass

                if value is True:
                    # since the condition is always true it can be replaced with None,
                    # but don't do this for if 1=1 statements since they are used as a workaround for the Kontakt 2 parser buffer overflow
                    if not self.is1equals1(condition):
                        condition = None

                    if len(stmts) > 0:
                        condition_stmts_tuples.append((condition, stmts))

                    break

                if not (value is False or len(stmts) == 0):
                    condition_stmts_tuples.append((condition, stmts))

            # if there's just an else statement left, return its statement list
            if len(condition_stmts_tuples) == 1 and condition_stmts_tuples[0][0] is None:
                return condition_stmts_tuples[0][1]
            elif len(condition_stmts_tuples) == 0:
                return []
            else:
                node.condition_stmts_tuples = condition_stmts_tuples
                return [node]
        else:
            return flatten([self.modify(stmt) for stmt in statements])

    def modifySelectStmt(self, node):
        statements = ASTModifier.modifySelectStmt(self, node)

        if len(statements) == 1:
            node = statements[0]

            try:
                value = evaluate_expression(node.expression)

                if value is None:
                    return [node]

                for ((start, stop), stmts) in node.range_stmts_tuples:
                    start = evaluate_expression(start)
                    stop = evaluate_expression(stop)

                    if (stop is not None and start <= value <= stop) or (start == value):
                        return stmts
            except ParseException:
                pass

            return [node]
        else:
            return flatten([self.modify(stmt) for stmt in statements])

    def modifyWhileStmt(self, node):
        statements = ASTModifier.modifyWhileStmt(self, node)

        if len(statements) == 1:
            node = statements[0]

            try:
                value = evaluate_expression(node.condition)

                if value is False:
                    return []
            except ParseException:
                pass
            return [node]
        else:
            return flatten([self.modify(stmt) for stmt in statements])

class ASTModifierRemoveUnusedFunctions(ASTModifier):
    '''Remove unused functions. Used if optimize mode is selected'''

    def __init__(self, module_ast, used_functions):
        ASTModifier.__init__(self, modify_expressions = False)
        self.used_functions = used_functions
        self.traverse(module_ast)

    def modifyModule(self, node, *args, **kwargs):
        # only keep used functions
        node.blocks = [b for b in node.blocks if isinstance(b, Callback) or b.name.identifier in self.used_functions]

class ASTModifierRemoveUnusedVariables(ASTModifier):
    '''Remove unused variables. Used if optimize mode is selected'''

    def __init__(self, module_ast, used_variables):
        ASTModifier.__init__(self)
        self.used_variables = used_variables
        self.traverse(module_ast)

    def modifyDeclareStmt(self, node):
        # only keep used variables
        statements = ASTModifier.modifyDeclareStmt(self, node)

        if len(statements) == 1:
            node = statements[0]
            is_ui_variable = node.modifiers is not None and any([m.lower().startswith('ui_') for m in node.modifiers])

            if not str(node.variable).lower() in self.used_variables and not is_ui_variable:
                return []
            else:
                return [node]
        else:
            return flatten([self.modify(stmt) for stmt in statements])