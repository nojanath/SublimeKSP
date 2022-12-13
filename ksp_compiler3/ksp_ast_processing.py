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
from ksp_builtins import string_typed_control_parameters, control_parameters, event_parameters
#import io

def stripNone(L):
    return [x for x in L if x is not None]

def stripFalse(L):
    return [x for x in L if x]

def flatten_iter(*args):
    for arg in args:
        try:
            for i in arg:
                for l in flatten(i):
                    yield l
        except TypeError:
            yield arg

def flatten(L):
    # for efficiency reasons, return the list itself it it doesn't contain any nested lists
    if not any([type(x) is list for x in L]):
        return L
    return list(flatten_iter(L))

def handle_set_par(control, parameter, value):
    # for converting integers to IDs. e.g e -> 4 := x
    if type(parameter) == Integer:
        parameter = ID(parameter.lexinfo, str(parameter))

    remap = {'X': 'POS_X', 'Y': 'POS_Y', 'MAX': 'MAX_VALUE', 'MIN': 'MIN_VALUE', 'DEFAULT': 'DEFAULT_VALUE'}
    cp = parameter.identifier.upper()
    cp = '$CONTROL_PAR_%s' % remap.get(cp, cp)
    if cp in control_parameters:
        control_par = VarRef(parameter.lexinfo, ID(parameter.lexinfo, cp))
        if cp in string_typed_control_parameters:
            func_name = 'set_control_par_str'
        else:
            func_name = 'set_control_par'
        return FunctionCall(control.lexinfo, ID(control.lexinfo, func_name),
                            parameters=[control, control_par, value], is_procedure=True)

    remap = {'PAR_0': '0', 'PAR_1': '1', 'PAR_2': '2', 'PAR_3': '3'}
    event_p = parameter.identifier.upper()
    event_p = '$EVENT_PAR_%s' % remap.get(event_p, event_p)
    if event_p in event_parameters:
        event_par = VarRef(parameter.lexinfo, ID(parameter.lexinfo, event_p))
        func_name = 'set_event_par'
        return FunctionCall(control.lexinfo, ID(control.lexinfo, func_name),
                            parameters=[control, event_par, value], is_procedure=True)

    raise Exception("%s is not a valid control_par/event_par" % parameter.identifier)

def handle_get_par(control, parameter):
    if type(parameter) == Integer:
        parameter = ID(parameter.lexinfo, str(parameter))

    remap = {'X': 'POS_X', 'Y': 'POS_Y', 'MAX': 'MAX_VALUE', 'MIN': 'MIN_VALUE', 'DEFAULT': 'DEFAULT_VALUE'}
    cp = parameter.identifier.upper()
    cp = '$CONTROL_PAR_%s' % remap.get(cp, cp)
    if cp in control_parameters:
        control_par = VarRef(parameter.lexinfo, ID(parameter.lexinfo, cp))
        if cp in string_typed_control_parameters:
            func_name = 'get_control_par_str'
        else:
            func_name = 'get_control_par'
        return FunctionCall(control.lexinfo, ID(control.lexinfo, func_name),
                            parameters=[control, control_par], is_procedure=False)

    remap = {'PAR_0': '0', 'PAR_1': '1', 'PAR_2': '2', 'PAR_3': '3'}
    event_p = parameter.identifier.upper()
    event_p = '$EVENT_PAR_%s' % remap.get(event_p, event_p)
    if event_p in event_parameters:
        event_par = VarRef(parameter.lexinfo, ID(parameter.lexinfo, event_p))
        func_name = 'get_event_par'
        return FunctionCall(control.lexinfo, ID(control.lexinfo, func_name),
                            parameters=[control, event_par], is_procedure=False)

    raise Exception("%s is not a valid control_par/event_par" % parameter.identifier)

class VariableNotDeclaredException(ParseException):
    pass

class ASTVisitor(object):
    def __init__(self, visit_expressions=True):
        self.node = None
        self._visit_expressions = visit_expressions
        self._cache = {}
        self.depth = -1

    def dispatch(self, parent, node, *args, **kwargs):
        if not self._visit_expressions and isinstance(node, Expr):
            return
        self.node = node
        klass = node.__class__
        meth = self._cache.get(klass, None)
        if meth is None:
            className = klass.__name__
            meth = getattr(self, 'visit' + className, self.visit_default)
            self._cache[klass] = meth
        self.depth += 1
        try:
            result = meth(parent, node, *args, **kwargs)

            if result is not False and not meth == self.visit_default:
                self.visit_children(parent, node, *args, **kwargs)
        finally:
            self.depth -= 1
        return

    def indent(self):
        return '  '*self.depth

    def visit_children(self, parent, node, *args, **kwargs):
        for child in node.get_childnodes():
            self.dispatch(node, child, *args, **kwargs)

    def visit_default(self, parent, node, *args, **kwargs):
        self.dispatch(parent, node, *args, **kwargs)

    def traverse(self, tree, *args, **kwargs):
        # Do walk of tree using visitor
        self.dispatch(parent=None, node=tree, *args, **kwargs)

    visit = dispatch
    visit_default = visit_children


class ASTModifier(object):
    def __init__(self, modify_expressions=True):
        self.node = None
        self._modify_expressions = modify_expressions
        self._cache = {}
        self.depth = -1

    def dispatch(self, node, *args, **kwargs):
        if not self._modify_expressions and isinstance(node, Expr):
            return node

        self.node = node
        klass = node.__class__
        meth = self._cache.get(klass, None)

        if meth is None:
            className = klass.__name__
            meth = getattr(self, 'modify' + className, None)
            self._cache[klass] = meth

        if meth is None:
            return node

        self.depth += 1

        try:
            return meth(node, *args, **kwargs)
        finally:
            self.depth -= 1

        return node

    def indent(self):
        return '  ' * self.depth

    def modify_default(self, node, *args, **kwargs):
        self.dispatch(node, *args, **kwargs)

    def modifyCallback(self, node, *args, **kwargs):
        node.variable = self.modify(node.variable, *args, **kwargs)
        node.lines = flatten([self.modify(l, *args, **kwargs) for l in node.lines])
        return node

    def modifyFunctionDef(self, node, *args, **kwargs):
        node.name = self.modify(node.name, *args, **kwargs)
        node.lines = flatten([self.modify(l, *args, **kwargs) for l in node.lines])
        return node

    def modifyFamilyStmt(self, node, *args, **kwargs):
        node.name = self.modify(node.name, *args, **kwargs)
        node.statements = flatten([self.modify(l, *args, **kwargs) for l in node.statements])
        return [node]

    def modifyAssignStmt(self, node, *args, **kwargs):
        node.varref = self.modify(node.varref, *args, **kwargs)
        node.expression = self.modify(node.expression, *args, **kwargs)
        return [node]

    def modifyPreprocessorCondition(self, node, *args, **kwargs):
        return [node]

    def modifyFunctionCall(self, node, *args, **kwargs):
        node.function_name = self.modify(node.function_name, *args, **kwargs)
        node.parameters = [self.modify(p, *args, **kwargs) for p in node.parameters]
        if node.is_procedure:
            return [node]
        else:
            return node

    def modifyPropertyDef(self, node, *args, **kwargs):
        node.name = self.modify(node.name, *args, **kwargs)
        if node.get_func_def:
            node.get_func_def = self.modify(node.get_func_def, *args, **kwargs)
        if node.set_func_def:
            node.set_func_def = self.modify(node.set_func_def, *args, **kwargs)
        return [node]

    def modifyWhileStmt(self, node, *args, **kwargs):
        node.statements = stripFalse(flatten([self.modify(s, *args, **kwargs) for s in node.statements]))
        node.condition = self.modify(node.condition, *args, **kwargs)
        return [node]

    def modifyIfStmt(self, node, *args, **kwargs):
        temp = []
        for (condition, stmts) in node.condition_stmts_tuples:
            condition = self.modify(condition, *args, **kwargs)
            stmts = flatten([self.modify(s, *args, **kwargs) for s in stmts])
            temp.append((condition, stmts))
        if not temp:
            return []
        else:
            node.condition_stmts_tuples = temp
            return [node]

    def modifyDeclareStmt(self, node, *args, **kwargs):
        if not (node.size is None):
            node.size = self.modify(node.size, *args, **kwargs)
        if type(node.initial_value) is list:
            node.initial_value = [self.modify(v, *args, **kwargs) for v in node.initial_value]
        elif node.initial_value:
            node.initial_value = self.modify(node.initial_value, *args, **kwargs)
        node.variable = self.modify(node.variable, *args, **kwargs)
        node.parameters = [self.modify(p, *args, **kwargs) for p in node.parameters]
        return [node]

    def modifySelectStmt(self, node, *args, **kwargs):
        node.expression = self.modify(node.expression, *args, **kwargs)
        range_stmts_tuples = []
        for ((start, stop), stmts) in node.range_stmts_tuples:
            start = self.modify(start, *args, **kwargs)
            stop = self.modify(stop, *args, **kwargs)
            stmts = flatten([self.modify(s, *args, **kwargs) for s in stmts])
            if stmts:
                range_stmts_tuples.append(((start, stop), stmts))
        if range_stmts_tuples:
            node.range_stmts_tuples = range_stmts_tuples
            return [node]
        else:
            return []

    def modifyBinOp(self, node, *args, **kwargs):
        node.left = self.modify(node.left, *args, **kwargs)
        node.right = self.modify(node.right, *args, **kwargs)
        return node

    def modifyUnaryOp(self, node, *args, **kwargs):
        node.right = self.modify(node.right, *args, **kwargs)
        return node

    def modifyVarRef(self, node, *args, **kwargs):
        node.subscripts = [self.modify(s, *args, **kwargs) for s in node.subscripts]
        node.identifier = self.modify(node.identifier, *args, **kwargs)
        return node

    def modifyModule(self, node, *args, **kwargs):
        node.blocks = flatten([self.modify(b, *args, **kwargs) for b in node.blocks])

    def traverse(self, tree, *args, **kwargs):
        # Do walk of tree using AST modifier
        self.dispatch(node=tree, *args, **kwargs)

    modify = dispatch