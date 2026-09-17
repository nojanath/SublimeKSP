# ksp-compiler - a compiler for the Kontakt script language
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

'''A faster variant of the PLY LR parsing loop for the KSP grammar.

It differs from ply.yacc.LRParser.parseopt with tracking enabled in two ways:
- Only line numbers are tracked, because the compiler never uses lexpos, endlineno or endlexpos.
- Rules whose action only passes on one symbol (p[0] = p[1] or p[0] = p[2]) or sets None are reduced
  without calling the action. These are detected by comparing the bytecode of each action with the templates below.
'''

import sys

from ply.yacc import LRParser, YaccSymbol, YaccProduction, call_errorfunc, error_count

PASS_FIRST = 1
PASS_SECOND = 2
PASS_NONE = 3

def template_pass_first(p):
    'template'
    p[0] = p[1]

def template_pass_second(p):
    'template'
    p[0] = p[2]

def template_pass_none(p):
    'template'
    p[0] = None

def template_pass_unchanged(p):
    'template'
    p[0] = p[0]

def code_signature(func):
    '''Returns the parts of a function's code object that define what it does (ignoring its docstring and line numbers)'''
    code = func.__code__
    consts = tuple(c for c in code.co_consts if c is not func.__doc__)

    return (code.co_code, consts, code.co_names, code.co_varnames, code.co_argcount)

template_kinds = [(code_signature(template_pass_first), PASS_FIRST, 1),
                  (code_signature(template_pass_second), PASS_SECOND, 2),
                  (code_signature(template_pass_none), PASS_NONE, 0),
                  (code_signature(template_pass_unchanged), PASS_NONE, 0)]

def pass_through_kind(production):
    '''Returns the kind of reduction the action of the production does if it only passes on a value, otherwise 0'''
    func = production.callable

    if func is None or not hasattr(func, '__code__'):
        return 0

    signature = code_signature(func)

    for template_signature, kind, min_len in template_kinds:
        if signature == template_signature and production.len >= min_len:
            return kind

    return 0

class LineNumberLRParser(LRParser):
    def parse(self, input=None, lexer=None, debug=False, tracking=False, tokenfunc=None):
        if tracking and not debug:
            return self.parse_tracking_line_numbers(input, lexer, tokenfunc)

        return LRParser.parse(self, input, lexer, debug, tracking, tokenfunc)

    def parse_tracking_line_numbers(self, input=None, lexer=None, tokenfunc=None):
        # Same as LRParser.parseopt with tracking, apart from the differences described at the top of this file
        productions = getattr(self, 'pass_through_productions', None)

        if productions is None or len(productions) != len(self.productions):
            productions = self.pass_through_productions = [(p.name, p.len, p.callable, pass_through_kind(p)) for p in self.productions]

        lookahead = None
        lookaheadstack = []
        actions = self.action
        goto = self.goto
        defaulted_states = self.defaulted_states
        pslice = YaccProduction(None)
        errorcount = 0

        if not lexer:
            from ply import lex
            lexer = lex.lexer

        pslice.lexer = lexer
        pslice.parser = self

        if input is not None:
            lexer.input(input)

        if tokenfunc is None:
            get_token = lexer.token
        else:
            get_token = tokenfunc

        self.token = get_token

        statestack = []
        self.statestack = statestack
        symstack = []
        self.symstack = symstack

        pslice.stack = symstack
        errtoken = None

        statestack.append(0)
        sym = YaccSymbol()
        sym.type = '$end'
        symstack.append(sym)
        state = 0

        while True:
            if state not in defaulted_states:
                if not lookahead:
                    if not lookaheadstack:
                        lookahead = get_token()
                    else:
                        lookahead = lookaheadstack.pop()

                    if not lookahead:
                        lookahead = YaccSymbol()
                        lookahead.type = '$end'

                t = actions[state].get(lookahead.type)
            else:
                t = defaulted_states[state]

            if t is not None:
                if t > 0:
                    # shift a symbol on the stack
                    statestack.append(t)
                    state = t
                    symstack.append(lookahead)
                    lookahead = None

                    if errorcount:
                        errorcount -= 1

                    continue

                if t < 0:
                    # reduce a symbol on the stack
                    pname, plen, callable, kind = productions[-t]
                    sym = YaccSymbol()
                    sym.type = pname

                    if plen:
                        if kind:
                            first = symstack[-plen]
                            sym.lineno = first.lineno

                            if kind == PASS_FIRST:
                                sym.value = first.value
                            elif kind == PASS_SECOND:
                                sym.value = symstack[-plen + 1].value
                            else:
                                sym.value = None

                            del symstack[-plen:]
                            del statestack[-plen:]
                            symstack.append(sym)
                            state = goto[statestack[-1]][pname]
                            statestack.append(state)
                            continue

                        sym.value = None
                        targ = symstack[-plen - 1:]
                        targ[0] = sym
                        sym.lineno = targ[1].lineno
                        pslice.slice = targ

                        try:
                            del symstack[-plen:]
                            self.state = state
                            callable(pslice)
                            del statestack[-plen:]
                            symstack.append(sym)
                            state = goto[statestack[-1]][pname]
                            statestack.append(state)
                        except SyntaxError:
                            lookaheadstack.append(lookahead)
                            symstack.extend(targ[1:-1])
                            statestack.pop()
                            state = statestack[-1]
                            sym.type = 'error'
                            sym.value = 'error'
                            lookahead = sym
                            errorcount = error_count
                            self.errorok = False

                        continue
                    else:
                        sym.value = None
                        sym.lineno = lexer.lineno

                        if kind:
                            symstack.append(sym)
                            state = goto[statestack[-1]][pname]
                            statestack.append(state)
                            continue

                        targ = [sym]
                        pslice.slice = targ

                        try:
                            self.state = state
                            callable(pslice)
                            symstack.append(sym)
                            state = goto[statestack[-1]][pname]
                            statestack.append(state)
                        except SyntaxError:
                            lookaheadstack.append(lookahead)
                            statestack.pop()
                            state = statestack[-1]
                            sym.type = 'error'
                            sym.value = 'error'
                            lookahead = sym
                            errorcount = error_count
                            self.errorok = False

                        continue

                if t == 0:
                    n = symstack[-1]
                    return getattr(n, 'value', None)

            if t is None:
                # error recovery, as in LRParser.parseopt
                if errorcount == 0 or self.errorok:
                    errorcount = error_count
                    self.errorok = False
                    errtoken = lookahead

                    if errtoken.type == '$end':
                        errtoken = None

                    if self.errorfunc:
                        if errtoken and not hasattr(errtoken, 'lexer'):
                            errtoken.lexer = lexer

                        self.state = state
                        tok = call_errorfunc(self.errorfunc, errtoken, self)

                        if self.errorok:
                            lookahead = tok
                            errtoken = None
                            continue
                    else:
                        if errtoken:
                            if hasattr(errtoken, 'lineno'):
                                lineno = lookahead.lineno
                            else:
                                lineno = 0

                            if lineno:
                                sys.stderr.write('yacc: Syntax error at line %d, token=%s\n' % (lineno, errtoken.type))
                            else:
                                sys.stderr.write('yacc: Syntax error, token=%s' % errtoken.type)
                        else:
                            sys.stderr.write('yacc: Parse error in input. EOF\n')
                            return
                else:
                    errorcount = error_count

                if len(statestack) <= 1 and lookahead.type != '$end':
                    lookahead = None
                    errtoken = None
                    state = 0
                    del lookaheadstack[:]
                    continue

                if lookahead.type == '$end':
                    return

                if lookahead.type != 'error':
                    sym = symstack[-1]

                    if sym.type == 'error':
                        sym.endlineno = getattr(lookahead, 'lineno', sym.lineno)
                        lookahead = None
                        continue

                    t = YaccSymbol()
                    t.type = 'error'

                    if hasattr(lookahead, 'lineno'):
                        t.lineno = t.endlineno = lookahead.lineno

                    if hasattr(lookahead, 'lexpos'):
                        t.lexpos = t.endlexpos = lookahead.lexpos

                    t.value = lookahead
                    lookaheadstack.append(lookahead)
                    lookahead = t
                else:
                    sym = symstack.pop()
                    lookahead.lineno = sym.lineno
                    statestack.pop()
                    state = statestack[-1]

                continue

            raise RuntimeError('yacc: internal parser error!!!\n')
