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
from ksp_builtins import string_typed_control_parameters
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

def handle_set_control_par(control, parameter, value):
    remap = {'X': 'POS_X', 'Y': 'POS_Y', 'MAX': 'MAX_VALUE', 'MIN': 'MIN_VALUE', 'DEFAULT': 'DEFAULT_VALUE'}
    cp = parameter.identifier.upper()
    cp = '$CONTROL_PAR_%s' % remap.get(cp, cp)
    control_par = VarRef(parameter.lexinfo, ID(parameter.lexinfo, cp))
    if cp in string_typed_control_parameters:
        func_name = 'set_control_par_str'
    else:
        func_name = 'set_control_par'
    return FunctionCall(control.lexinfo, ID(control.lexinfo, func_name),
                        parameters=[control, control_par, value], is_procedure=True)

def handle_get_control_par(control, parameter):
    remap = {'X': 'POS_X', 'Y': 'POS_Y', 'MAX': 'MAX_VALUE', 'MIN': 'MIN_VALUE', 'DEFAULT': 'DEFAULT_VALUE'}
    cp = parameter.identifier.upper()
    cp = '$CONTROL_PAR_%s' % remap.get(cp, cp)
    control_par = VarRef(parameter.lexinfo, ID(parameter.lexinfo, cp))
    if cp in string_typed_control_parameters:
        func_name = 'get_control_par_str'
    else:
        func_name = 'get_control_par'
    return FunctionCall(control.lexinfo, ID(control.lexinfo, func_name),
                        parameters=[control, control_par], is_procedure=False)

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
            #print meth
            #print result != False and not meth == self.visit_default
            if result is not False and not meth == self.visit_default:
                #print 'visit children'
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
        """Do walk of tree using visitor"""
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
            ##print 'modify' + className, node
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
        return '  '*self.depth

    def modify_default(self, node, *args, **kwargs):
        self.dispatch(node, *args, **kwargs)

    def modifyCallback(self, node, *args, **kwargs):
        node.ui_control = self.modify(node.ui_control, *args, **kwargs)
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
        """Do walk of tree using AST modifier"""
        self.dispatch(node=tree, *args, **kwargs)

    modify = dispatch


##
##class ASTVisitorDotGenerator(ASTVisitor):
##    def __init__(self, ast):
##        ASTVisitor.__init__(self, visit_expressions=True)
##        self.output = StringIO.StringIO()
##        self.traverse(ast)
##    def name_of(self, node):
##        if node:
##            if isinstance(node, ID):
##                return node.identifier
##            else:
##                return ASTNode.__str__(node)
##        else:
##            return 'None'
##    def visit_default(self, parent, node, *args, **kwargs):
##        if parent is None:
##            n1 = self.name_of(parent)
##        else:
##            n1 = self.name_of(parent) + ' -> '
##        n2 = self.name_of(node)
##        if parent:
##            self.output.write('  %s%s -> %s;\n' % (self.indent(), id(parent), id(node)))
##        else:
##            self.output.write('  %s%s\n' % (self.indent(), id(node)))
##        self.output.write('  %s%s [label="%s"]\n' % (self.indent(), id(node), self.name_of(node)))
##    def get_dot_output(self):
##        return 'digraph G {rankdir=LR;ordering=out;size="10,40"; \n%s\n}' % self.output.getvalue()
##
##class Symbol:
##    def __init__(self, name, type):
##        self.name = name
##        self.type = type
##    def __str__(self):
##        return self.name
##
##class Variable(Symbol):
##    def __init__(self, name, vartype='$'):
##        Symbol.__init__(self, name, type='variable')
##
##class Family(Symbol):
##    def __init__(self, name):
##        Symbol.__init__(self, name, type='family')
##        self.env = None # members environment
##
##class Environment:
##    def __init__(self, parent_env = None):
##        self.dict = {}
##        self.parent_env = parent_env
##        self.level = 'module'
##        self.declarations_allowed = True
##        self.namespace = ''
##
##    def debug_print(self, name='', depth=0):
##        indent = depth * '  '
##        print indent, 'environment(%s - %s)' % (name, self.level)
##        for (name, value) in self.dict.iteritems():
##            if isinstance(value, Environment):
##                value.debug_print(name, depth+1)
##            else:
##                print indent+'  ', name
##
##    def new_scope(self, level, declarations_allowed=True, family=None, namespace=''):  # level may be any of 'module', 'function', 'family'
##        e = Environment(parent_env = self)
##        e.level = level
##        e.declarations_allowed = declarations_allowed
##        e.namespace = ''
##        if family:
##            family.env = e
##            e.namespace = unicode(family.name)
##        return e
##
##    def put(self, name, value, top_level = False):
##        if not self.declarations_allowed:
##            raise ParseException('Declarations not allowed here')
##        if self.redeclared(name):
##            raise ParseException('Symbol already declared: %s' % name)
##        env = self
##        while env.level not in ['module', 'family']:
##            env = env.parent_env
##        env.dict[name] = value
##
##    def redeclared(self, name):
##        try:
##            (env, symbol) = self._get(name)
##            print env.level, self.level
##            return (env.level == self.level)  # name clash if same environment level
##        except VariableNotDeclaredException:
##            return False
##
##    def _get(self, name):
##        'returns (environment, symbol)-tuple where symbol has the given name'
##        if not name in self.dict:
##            if self.parent_env:
##                return self.parent_env._get(name)
##            else:
##                raise VariableNotDeclaredException('Symbol not declared: %s' % name)
##        return (self, self.dict[name])
##
##    def get(self, name):
##        env, symbol = self._get(name)
##        return symbol
##
##class ASTVisitorEnv(ASTVisitor):
##    def __init__(self, ast):
##        ASTVisitor.__init__(self, visit_expressions=False)
##        self.traverse(ast)
##    def visitModule(self, parent, node, *args, **kwargs):
##        node.env = Environment()
##    def visitFunctionDef(self, parent, node, *args, **kwargs):
##        node.env = parent.env.new_scope('function')
##    def visitCallback(self, parent, node, *args, **kwargs):
##        declarations_allowed = (node.name == 'init')
##        node.env = parent.env #.new_scope('module', declarations_allowed)
##    def visitFamilyStmt(self, parent, node, *args, **kwargs):
##        family = Family(node.name)
##        parent.env.put(node.name, family)
##        node.env = parent.env.new_scope('family', declarations_allowed=parent.env.declarations_allowed, family=family)
##    def visitDeclareStmt(self, parent, node, *args, **kwargs):
##        name = node.variable.identifier
##        if node.variable.prefix:
##            vartype = node.variable.prefix
##        elif node.size:
##            vartype = '%'
##        else:
##            vartype = '$'
##        node.env = parent.env
##        node.env.put(name, Variable(name, vartype))
##    def visit_default(self, parent, node, *args, **kwargs):
##        node.env = parent.env
##
##
