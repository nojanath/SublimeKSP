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

from ksp_compiler import KSPCompiler
from ksp_parser import parse
import unittest

def default_read_file_func(filepath):
    return open(filepath, 'r').read()

def do_compile(code, compact=True, compactVars=False, comments_on_expansion=True, read_file_func=default_read_file_func, extra_syntax_checks=True, optimize=False, check_empty_compound_statements=False):
    compiler = KSPCompiler(code, compact, compactVars, comments_on_expansion, read_file_func=read_file_func, extra_syntax_checks=extra_syntax_checks, optimize=optimize, check_empty_compound_statements=check_empty_compound_statements)
    compiler.compile()
    return compiler.compiled_code.replace('\r', '')

class TestClass(unittest.TestCase):
    # def test1(self):
    #     code = '''
    #         on init
    #             declare x
    #             x := 10
    #         end on'''
    #     parse(code)
        #output = do_compile(code)
        #self.assertTrue('$x := 10' in output)

    def testSubscripts1(self):
        code = '''
        function double(x) -> result
            result := x*2
          end function

        on init
          message(double(5))
        end on
        '''
        parse(code)
        #output = do_compile(code, optimize=True)
        #self.assertTrue('%data[34] := 99' in output)
        #self.assertTrue('message(%data[34])' in output)

if __name__ == "__main__":
    unittest.main()

