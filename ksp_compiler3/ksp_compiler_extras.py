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
user_defined_functions = {}
key_ids = {}

pgs_functions = set(['_pgs_create_key', '_pgs_key_exists', '_pgs_set_key_val', '_pgs_get_key_val',
                     'pgs_create_key',  'pgs_key_exists',  'pgs_set_key_val', 'pgs_get_key_val',
                     'pgs_create_str_key', 'pgs_str_key_exists', 'pgs_set_str_key_val', 'pgs_get_str_key_val'])

mark_constant_re = re.compile(r'MARK_\d+')

def clear_symbol_table():
    symbol_table.clear()
    key_ids.clear()
    user_defined_functions.clear()

class ValueUndefinedException(ParseException):
    def __init__(self, node, msg='Value of variable undefined'):
        ParseException.__init__(self, node, msg)

class Variable:
    def __init__(self, name, size=1, params=None, control_type=None, is_constant=False, is_polyphonic=False, value=None):
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
    i &= (1 << bits) - 1  # get last "bits" bits, as unsigned
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

def evaluate_expression(expr):
    if isinstance(expr, BinOp):
        a, b = evaluate_expression(expr.left), evaluate_expression(expr.right)
        op = expr.op
        if op in ['+', '-', '*', '/', '<', '<=', '>', '>=', '=', '#', '.and.', '.or.', 'mod']:
            a, b = int(a), int(b)
            if op == '+':
                return toint(a + b)
            elif op == '-':
                return toint(a - b)
            elif op == '*':
                return toint(a * b)
            elif op == '/':
                return int(math.copysign(abs(a) // abs(b), a / b)) # a // b yields the wrong result in case of negative numbers, eg. -10/9
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
            elif op == '.and.':
                return a & b
            elif op == '.or.':
                return a | b
            elif op == 'mod':
                result = abs(a) % abs(b)
                if a < 0:
                    return -result
                else:
                    return result
        elif op == '&':
            return str(a) + str(b)
        elif op in ['and', 'or']:
            a, b = bool(a), bool(b)
            #if type(a) is not bool:
            #    raise ParseException(expr.left, 'Boolean expected.')
            #if type(b) is not bool:
            #    raise ParseException(expr.right, 'Boolean expected.')
            if op == 'and':
                return a and b
            else:
                return a or b
    elif isinstance(expr, UnaryOp):
        a = int(evaluate_expression(expr.right))
        if expr.op == '-':
            return toint(-a)
        elif expr.op == '.not.':
            return toint(0xFFFFFFFF ^ a)
    elif isinstance(expr, Number) or isinstance(expr, String):
        return expr.value
    elif isinstance(expr, VarRef):
        name = str(expr.identifier)
        if name.lower() not in symbol_table:
            ##import traceback
            ##traceback.print_stack()
            ##print name.lower(), [v for v in symbol_table if 'num_types' in v]
            raise ParseException(expr, 'Variable not declared: %s' % name)
        value = symbol_table[name.lower()].value
        if value is None:
            raise ValueUndefinedException(expr)
        if len(expr.subscripts) > 1:
            raise ParseException(expr, 'More than one subscript: %s' % str(expr))
        if expr.subscripts:
            subscript = int(evaluate_expression(expr.subscripts[0]))
        else:
            subscript = None
        if (expr.identifier.prefix in '%!') != (subscript is not None):
            raise ParseException(expr, 'Use of subscript wrong.')
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
        funcs2numparameters = {'abs': 1, 'in_range': 3, 'sh_left': 2, 'sh_right': 2, 'by_marks': 1}
        if name in list(funcs2numparameters.keys()):
            if len(parameters) != funcs2numparameters[name]:
                raise ParseException(expr, 'Wrong number of parameters to %s' % name)
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
        raise ValueUndefinedException(expr, 'Constant value expected.')

def assert_type(node, type):
    if node is None:
        node_type = 'None'
        raise Exception()
    node_type = node.type
    if node_type != type:
        raise ParseException(node, 'Expected expression of %s type, got %s.' % (type, node_type))

class ASTVisitorDetermineExpressionTypes(ASTVisitor):

    def __init__(self, ast):
        ASTVisitor.__init__(self)
        self.traverse(ast)

    def visitFunctionCall(self, parent, node, *args):
        self.visit_children(parent, node, *args)
        function_name = node.function_name.identifier
        if function_name in ksp_builtins.function_signatures:
            params, return_type = ksp_builtins.function_signatures[function_name]
            if type:
                node.type = return_type
            else:
                node.type = 'undefined'
            passed_params = node.parameters
            if len(passed_params) != len(params):
                raise ParseException(node, 'Wrong number of parameters for %s: expected %d, got %d' % (function_name, len(params), len(passed_params)))
            for (param_descriptor, passed_param) in zip(params, passed_params):
                param_descriptor = param_descriptor.replace('<', '').replace('>', '')
                is_text = 'text' in param_descriptor or param_descriptor.endswith('name') or param_descriptor.endswith('-path')
                if not is_text:
                    if 'array-or-string-array-variable' in param_descriptor:
                        pass
                    elif 'string-array' in param_descriptor:
                        assert_type(passed_param, 'array of string')
                    elif 'array-variable' in param_descriptor:
                        assert_type(passed_param, 'array of integer')
                    elif 'key-id' in param_descriptor:
                        if not isinstance(passed_param, VarRef):
                            raise ParseException(node, 'Expected key-id.')
                        passed_param.type = 'key-id'
                    elif not 'variable' in param_descriptor:
                        assert_type(passed_param, 'integer')
        return False

    def visitBinOp(self, parent, expr, *args):
        self.visit_children(parent, expr, *args)
        #print expr.left.type, expr.op, expr.right.type
        if expr.op == '&':
            expr.type = 'string'
        elif expr.op in ('+', '-', '*', '/', 'mod', '.and.', '.or.'):
            assert_type(expr.left, 'integer')
            assert_type(expr.right, 'integer')
            expr.type = 'integer'
        elif expr.op in '< <= > >= = #':
            assert_type(expr.left, 'integer')
            assert_type(expr.right, 'integer')
            expr.type = 'boolean'
        elif expr.op in 'and or':
            assert_type(expr.left, 'boolean')
            assert_type(expr.right, 'boolean')
            expr.type = 'boolean'
        else:
            raise Exception()
        return False

    def visitUnaryOp(self, parent, expr, *args):
        self.visit_children(parent, expr, *args)
        if expr.op in ('-', '.not.'):
            assert_type(expr.right, 'integer')
            expr.type = 'integer'
        elif expr.op == 'not':
            assert_type(expr.right, 'boolean')
            expr.type = 'boolean'
        return False

    def visitNumber(self, parent, expr, *args):
        expr.type = 'integer'

    def visitString(self, parent, expr, *args):
        expr.type = 'string'

    def visitRawArrayInitializer(self, parent, expr, *args):
        expr.type = 'array of integer'

    def visitID(self, parent, expr, *args):
        if expr.prefix:
            expr.type = {'$': 'integer',
                         '%': 'array of integer',
                         '@': 'string',
                         '!': 'array of string'}[expr.prefix]
        else:
            expr.type = 'integer' # function return value

    def visitVarRef(self, parent, expr, *args):
        self.visit_children(parent, expr, *args)
        if expr.subscripts:
            assert_type(expr.subscripts[0], 'integer')
            if not expr.identifier.type.startswith('array'):
                raise ParseException(expr.identifier, 'Expected array')
            expr.type = expr.identifier.type.replace('array of ', '')
        else:
            expr.type = expr.identifier.type
        return False

class ASTVisitorCheckNoEmptyIfCaseStatements(ASTVisitor):
    def __init__(self, ast):
        ASTVisitor.__init__(self, visit_expressions=False)
        self.traverse(ast)

    def visitIfStmt(self, parent, node, *args):
        (condition, stmts) = node.condition_stmts_tuples[0]
        if len(stmts) == 0:
            raise ParseException(node, 'Warning: due to a ksp bug an empty if-statement is equivalent to invoking the exit function. Please make sure the body of your if-statement is not empty.')

    def visitSelectStmt(self, parent, node, *args):
        for ((start, stop), stmts) in node.range_stmts_tuples:
            if len(stmts) == 0:
                raise ParseException(start, 'Warning: due to a ksp bug an empty case-statement is equivalent to invoking the exit function. Please make sure the body of your case-statement is not empty.')

class ASTVisitorCheckStatementExprTypes(ASTVisitor):
    def __init__(self, ast):
        ASTVisitor.__init__(self, visit_expressions=False)
        self.traverse(ast)

    def visitDeclareStmt(self, parent, node, *args):
        if node.initial_value and not (type(node.initial_value) is list):
            assert_type(node.initial_value, node.variable.type)
        if node.size:
            assert_type(node.size, 'integer')

    def visitAssignStmt(self, parent, node, *args):
        # assigning an integer to a string variable is ok, so don't treat that as an error
        if not (node.expression and node.expression.type == 'integer' and node.varref.type == 'string'):
            assert_type(node.expression, node.varref.type)

    def visitWhileStmt(self, parent, node, *args):
        assert_type(node.condition, 'boolean')

    def visitForStmt(self, parent, node, *args):
        assert_type(node.loopvar, 'integer')
        assert_type(node.start, 'integer')
        assert_type(node.end, 'integer')
        if node.step:
            assert_type(node.step, 'integer')

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
    def __init__(self, ast, used_variables_set):
        ASTVisitor.__init__(self)
        self.used_variables = used_variables_set
        self.traverse(ast)

    def visitDeclareStmt(self, parent, node, *args):
        for child in node.get_childnodes()[1:]:  # visit all children but the first one (the declared variable)
            self.dispatch(node, child, *args)
        return False

    def visitID(self, parent, node, *args):
        self.used_variables.add(str(node).lower())
        return False

class ASTVisitorFindUsedFunctions(ASTVisitor):
    def __init__(self, ast, used_functions):
        ASTVisitor.__init__(self, visit_expressions=False)
        self.call_graph = {}
        self.traverse(ast)

        self.mark_used_functions_using_depth_first_traversal(self.call_graph, visited=used_functions)

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

    def mark_used_functions_using_depth_first_traversal(self, call_graph, start_node=None, visited=None):
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
            for child in node.get_childnodes()[1:]:  # visit all children but the first one (the key-id)
                self.dispatch(node, child, *args)
            return False

    def visitFunctionDef(self, parent, node, *args):
        if node.name.identifier in user_defined_functions:
            raise ParseException(node, 'There is already a variable/function defined with the same name')
        user_defined_functions[node.name.identifier] = node
        return True

    def visitDeclareStmt(self, parent, node, *args):
        name = str(node.variable)
        is_ui_control = [x for x in node.modifiers if x.startswith('ui_')]
        if is_ui_control:
            self.assert_true(not 'const' in node.modifiers,      node, 'A UI control cannot be constant')
            self.assert_true(not 'polyphonic' in node.modifiers, node, 'A UI control cannot be polyphonic')
        if 'ui_label' in node.modifiers:
            self.assert_true(node.parameters and len(node.parameters) == 2, node, 'Expected two parameters')
        elif 'ui_button' in node.modifiers or 'ui_menu' in node.modifiers or 'ui_switch' in node.modifiers:
            self.assert_true(not node.parameters, node, "Syntax error, didn't expect any parameter")
        elif 'ui_slider' in node.modifiers:
            self.assert_true(node.parameters and len(node.parameters) == 2, node, 'Expected two parameters: min, max')
        elif 'ui_knob' in node.modifiers or 'ui_value_edit' in node.modifiers:
            self.assert_true(node.parameters and len(node.parameters) == 3, node, 'Expected three parameters: min, max, scale')
        elif 'ui_table' in node.modifiers:
            self.assert_true(node.parameters and len(node.parameters) == 3, node, 'Expected three parameters: width, height, max')
        elif 'ui_waveform' in node.modifiers:
            self.assert_true(node.parameters and len(node.parameters) == 2, node, 'Expected two parameters: width, height')
        if name.lower() in symbol_table:
            raise ParseException(node.variable, 'Redeclaration of %s' % name)
        if node.size:
            try:
                size = evaluate_expression(node.size)
            except ValueUndefinedException:
                raise ParseException(node.size, 'Array size is non-constant or uses undefined variables')
        else:
            size = 1
        initial_value = None
        if 'const' in node.modifiers:
            if not node.initial_value:
                raise ParseException(node.variable, 'A constant value has to be assigned to the constant')
            try:
                initial_value = evaluate_expression(node.initial_value)
            except ValueUndefinedException:
                raise ParseException(node.initial_value, 'Expression uses non-constant values or undefined constant variables')
        try:
            params = []
            for param in node.parameters:
                # VALUE_EDIT_MODE_NOTE_NAMES is used in declare statements, but don't force a known value to evaluate to when it's used as a param
                if True or isinstance(param, VarRef) and (param.identifier.prefix+param.identifier.identifier in ['VALUE_EDIT_MODE_NOTE_NAMES', '$VALUE_EDIT_MODE_NOTE_NAMES']
                                                          or param.identifier.prefix+param.identifier.identifier in ksp_builtins.variables):
                    params.append(param)
                else:
                    params.append(evaluate_expression(param))
        except ValueUndefinedException:
            raise ParseException(node, 'Expression uses non-constant values or undefined constant variables')
        #name, size=1, params=None, control_type=None, is_constant=False, value=None):
        if is_ui_control:
            control_type = is_ui_control[0]
        else:
            control_type = None
        is_constant = 'const' in node.modifiers
        is_polyphonic = 'polyphonic' in node.modifiers
        symbol_table[name.lower()] = Variable(node.variable, size, params, control_type, is_constant, is_polyphonic, initial_value)
        self.visit_children(parent, node, *args)
        return False

    def visitID(self, parent, node, *args):
        name = str(node)
        special_names = ['NO_SYS_SCRIPT_RLS_TRIG', 'NO_SYS_SCRIPT_PEDAL', 'NO_SYS_SCRIPT_GROUP_START', 'NO_SYS_SCRIPT_ALL_NOTES_OFF']
        if not name in ksp_builtins.variables and not name in ksp_builtins.functions and not name.lower() in symbol_table and not name in special_names and not name in user_defined_functions:
            raise ParseException(node, 'Undeclared variable/function: %s' % name)


class ASTModifierSimplifyExpressions(ASTModifier):
    def __init__(self, module_ast, replace_constants=True):
        ASTModifier.__init__(self)
        self.replace_constants = replace_constants
        self.traverse(module_ast)

    def evaluate_expression_or_same(self, expr):
        if expr is None:
            return None
        try:
            result = evaluate_expression(expr)
            if type(result) is int and not isinstance(expr, Number):
                return Number(expr.lexinfo, result)
        except SyntaxError:
            pass
        return expr

    def modifyDeclareStmt(self, node):
        ASTModifier.modifyDeclareStmt(self, node)
        if 'const' in node.modifiers and self.replace_constants:
            return []
        else:
            return [node]

    def modifyBinOp(self, node):
        node = ASTModifier.modifyBinOp(self, node)
        node.left = self.evaluate_expression_or_same(node.left)
        node.right = self.evaluate_expression_or_same(node.right)
        return self.evaluate_expression_or_same(node)

    def modifyUnaryOp(self, node):
        node = ASTModifier.modifyUnaryOp(self, node)
        node.right = self.evaluate_expression_or_same(node.right)
        return self.evaluate_expression_or_same(node)

    def modifyVarRef(self, node):
        node = ASTModifier.modifyVarRef(self, node)
        if self.replace_constants and not mark_constant_re.match(node.identifier.identifier):  # MARK_%d constants are included in the symbol table in order to be possible to use on declaration lines, don't replace them with their values
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

class ASTModifierRemoveUnusedBranches(ASTModifier):
    def __init__(self, module_ast):
        ASTModifier.__init__(self)
        self.traverse(module_ast)

    def is1equals1(self, node):
        return isinstance(node, BinOp) and isinstance(node.left, Number) and isinstance(node.right, Number) and node.left.value == 1 and node.right.value == 1

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
    def __init__(self, module_ast, used_functions):
        ASTModifier.__init__(self, modify_expressions=False)
        self.used_functions = used_functions
        self.traverse(module_ast)

    def modifyModule(self, node, *args, **kwargs):
        ''' only keep used functions '''
        node.blocks = [b for b in node.blocks if isinstance(b, Callback) or b.name.identifier in self.used_functions]

class ASTModifierRemoveUnusedVariables(ASTModifier):
    def __init__(self, module_ast, used_variables):
        ASTModifier.__init__(self)
        self.used_variables = used_variables
        self.traverse(module_ast)

    def modifyDeclareStmt(self, node):
        ''' only keep used variables '''
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

class ASTModifierFixCallbug(ASTModifier):
    def __init__(self, module_ast, used_variables):
        ASTModifier.__init__(self, modify_expressions=False)

        self.dummy_assign = None  # dummy assignment statement, eg. $i = $i (using some variable $i that it finds in the script)

        self.pass_num = 1
        self.traverse(module_ast)
        self.pass_num = 2
        self.traverse(module_ast)

    def modifyDeclareStmt(self, node):
        # try to find some variable to use in dummy assignment
        if self.dummy_assign is None and self.pass_num == 1 and node.variable.type == 'integer' and 'const' not in node.modifiers:
            lexinfo = node.lexinfo
            varref = VarRef(lexinfo, node.variable)
            self.dummy_assign = AssignStmt(lexinfo, varref, varref)
        return [node]

    def fixStatementList(self, statements):
        # add a dummy assignment to the end of the list if the last element is a function call using "call"
        result = statements[:]
        if len(statements) > 0 and isinstance(statements[-1], FunctionCall) and statements[-1].using_call_keyword:
            if self.dummy_assign:
                result.append(self.dummy_assign)
            else:
                raise ParseException(statements[-1], 'The compiler needs to add a dummy assignment (eg. $x := $x) after this line, but could not find any integer variables to use for this purpose. Please declare one.')
        return result

    def modifyIfStmt(self, node):
        if self.pass_num == 2:
            node = ASTModifier.modifyIfStmt(self, node)[0]
            node.condition_stmts_tuples = [(condition, self.fixStatementList(stmts)) for (condition, stmts) in node.condition_stmts_tuples]
        return [node]

    def modifyWhileStmt(self, node):
        if self.pass_num == 2:
            node = ASTModifier.modifyWhileStmt(self, node)[0]
            node.statements = self.fixStatementList(node.statements)
        return [node]

    def modifySelectStmt(self, node):
        if self.pass_num == 2:
            node = ASTModifier.modifySelectStmt(self, node)[0]
            node.range_stmts_tuples = [(range, self.fixStatementList(statements)) for (range, statements) in node.range_stmts_tuples]
        return [node]

    def modifyFunctionDef(self, node):
        if self.pass_num == 2:
            node = ASTModifier.modifyFunctionDef(self, node)
            node.lines = self.fixStatementList(node.lines)
        return node

def check_code(module, optimize=False, check_empty_compound_statements=False, call_bug_work_around=True):
    clear_symbol_table()
    used_variables = set()

    if optimize:
        rescaler = 1/0.60
    else:
        rescaler = 1.0

    yield ('progress', 'checking types', int(40*rescaler))
    ASTVisitorDetermineExpressionTypes(module)

    yield ('progress', 'checking types', int(50*rescaler))
    ASTVisitorCheckStatementExprTypes(module)

    yield ('progress', 'checking declarations', int(60*rescaler))
    ASTVisitorCheckDeclarations(module)

    ##if call_bug_work_around:
    ##    yield ('progress', 'automatically introducing work-around for call bug', int(68*rescaler))
    ##    ASTModifierFixCallbug(module, used_variables)

    if optimize:
        yield ('progress', 'optimizing - simplying expressions', 70)
        ASTModifierSimplifyExpressions(module, replace_constants=True)

        yield ('progress', 'optimizing - removing unused code branches', 80)
        ASTModifierRemoveUnusedBranches(module)

        yield ('progress', 'optimizing - removing unused variables', 90)
        ASTVisitorFindUsedVariables(module, used_variables)

        yield ('progress', 'optimizing - removing unused variables', 95)
        ASTModifierRemoveUnusedVariables(module, used_variables)

    if check_empty_compound_statements:
        yield ('progress', 'checking existance of empty compound statements', 98)
        ASTVisitorCheckNoEmptyIfCaseStatements(module)

    yield ('completed', module)
