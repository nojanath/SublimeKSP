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

from ksp_compiler import ParseException, KSPCompiler
import os.path
import unittest

# To use cmd line: python -m unittest
# To test classes: python -m unittest -k Callbacks
# Ctrl/Cmd+B to run in IDE


def do_compile(code,
               remove_preprocessor_vars  = False,
               compact                   = True,
               compact_variables         = False,
               combine_callbacks         = True,
               extra_syntax_checks       = True,
               optimize                  = False,
               add_compiled_date_comment = False):

    compiler = KSPCompiler(code,
                           os.path.dirname(__file__),
                           compact                   = compact,
                           compact_variables         = compact_variables,
                           combine_callbacks         = combine_callbacks,
                           extra_syntax_checks       = extra_syntax_checks,
                           optimize                  = optimize,
                           add_compiled_date_comment = add_compiled_date_comment)
    compiler.compile()
    output_code = compiler.compiled_code

    if remove_preprocessor_vars and optimize == False:
        output_code = output_code.split('\n')
        del output_code[1:6]
        output_code = '\n'.join(output_code)

    output_code = output_code.replace('\r', '')

    return output_code

def assert_equal(self, output, expected_output):
    output = [l.strip() for l in output.split('\n') if l]
    expected_output = [l.strip() for l in expected_output.split('\n') if l]
    self.assertEqual(output, expected_output)

class Callbacks(unittest.TestCase):
    def testUIControlCallbackWithinOnInit(self):
        code = '''
            on init
                do_declare(5) { this callback should be moved out to the top-level }
            end on

            macro do_declare(param)
                declare ui_button b
                on ui_control(b)
                    message(param)
                end on
            end macro'''

        expected_output = '''
            on init
                declare ui_button $b
            end on

            on ui_control($b)
                message(5)
            end on'''

        output = do_compile(code, remove_preprocessor_vars = True)
        assert_equal(self, output, expected_output)

    def testUIControlCallbackWithinOnInitNestedMacros(self):
        code = '''
            on init
                do_declare(b) { this callback should be moved out to the top-level }
            end on

            macro nested(name)
                declare ui_button name
                on ui_control(name)
                    message(name)
                end on
            end macro

            macro do_declare(name)
                nested(name)
            end macro'''

        expected_output = '''
            on init
                declare ui_button $b
            end on
            on ui_control($b)
                message($b)
            end on'''

        output = do_compile(code, remove_preprocessor_vars = True)
        assert_equal(self, output, expected_output)

    def testCombineCallbacks(self):
        code = '''
            on init
                declare x := 1
            end on

            on init
                declare y := 1
            end on'''

        expected_output = '''
            on init
                declare $x := 1
                declare $y := 1
            end on'''

        output = do_compile(code, combine_callbacks = True, remove_preprocessor_vars = True)
        assert_equal(self, output, expected_output)

    def testCombineUICallbacks(self):
        code = '''
            on init
                declare ui_button test
            end on

            on ui_control (test)
                message("Callback One")
            end on

            on ui_control (test)
                message("Callback Two")
            end on'''

        expected_output = '''
            on init
              declare ui_button $test
            end on

            on ui_control($test)
              message("Callback One")
              message("Callback Two")
            end on'''

        output = do_compile(code, combine_callbacks = True, remove_preprocessor_vars = True)
        assert_equal(self, output, expected_output)

    def testCombineCallbackWithImportedFiles(self):
        code = '''
            import "test_imports/ui_cb_test_import.ksp" as f

            on init
                {If imported without namespace, then should throw error 'redeclaration of $mySwitch'}
                declare ui_switch mySwitch
            end on

            on ui_control (mySwitch)
                message("switch")
            end on

            on midi_in
                message("midi in main")
            end on'''

        expected_output = '''
            on init
              declare ui_switch $f__mySwitch
              declare ui_switch $mySwitch
            end on
            on ui_control($f__mySwitch)
              message("imported")
              message("switch")
            end on
            on midi_in
              message("midi on imported")
              message("midi in main")
            end on'''

        output = do_compile(code, combine_callbacks = True, remove_preprocessor_vars = True)
        assert_equal(self, output, expected_output)

    def testCombineCallbacksWithEmptyFunction(self):
        code = '''
            on init
                declare ui_button Button
            end on

            function foo()
            end function

            on ui_control (Button)
                call foo()
            end on
            '''

        expected_output = '''
            on init
              declare ui_button $Button
            end on

            function foo
            end function

            on ui_control($Button)
              call foo
            end on'''

        output = do_compile(code, combine_callbacks = True, remove_preprocessor_vars = True)
        assert_equal(self, output, expected_output)

class Precedence(unittest.TestCase):
    def testBinaryPrecedence1(self):
        code = '''
            on init
                declare x
                declare y
                declare z
                message((x .or. y) .and. z)
            end on'''

        expected_output = '''
            on init
            declare $x
            declare $y
            declare $z
            message(($x .or. $y) .and. $z)
            end on'''

        output = do_compile(code, remove_preprocessor_vars = True)
        assert_equal(self, output, expected_output)

class VariableNotDeclared(unittest.TestCase):
    def testUndeclaredVariableInOnInit(self):
        code = '''
            on init
                declare x
                y := x
            end on'''

        self.assertRaises(ParseException, do_compile, code)

    def testVariableUsedBeforeDeclaration(self):
        code = '''
        on init
            x := 5
            declare x
        end on'''

        self.assertRaises(ParseException, do_compile, code)

    def testFirstParamOfPGSFunctionsNotSeenAsUndeclared(self):
        code = '''
            on init
                pgs_create_key(my_pgs_var, 10)
                if pgs_key_exists(my_pgs_var)
                    pgs_set_key_val(my_pgs_var, 1, pgs_get_key_val(my_pgs_var, 0)+1)
                end if

                _pgs_create_key(my_pgs_var, 10)
                if _pgs_key_exists(my_pgs_var)
                    _pgs_set_key_val(my_pgs_var, 1, _pgs_get_key_val(my_pgs_var, 0)+1)
                end if

                pgs_create_str_key(PG)
                if pgs_str_key_exists(PG)
                    pgs_set_str_key_val(PG, pgs_get_str_key_val(PG))
                end if
            end on'''

        do_compile(code, compact_variables = True)

    def testFirstParamOfConditionNotSeenAsUndeclared(self):
        code = '''
            on init
                SET_CONDITION(my_condition)
                RESET_CONDITION(my_condition)
            end on'''

        do_compile(code, compact_variables = True)

    def testFirstParamOfUseCodeIfNotSeenAsUndeclared(self):
        code = '''
            on init
                SET_CONDITION(my_condition)
                USE_CODE_IF(my_condition)
                    message(5)
                END_USE_CODE
                USE_CODE_IF_NOT(my_condition)
                    message(6)
                END_USE_CODE

                RESET_CONDITION(my_condition)
                USE_CODE_IF(my_condition)
                    message(7)
                END_USE_CODE
                USE_CODE_IF_NOT(my_condition)
                    message(8)
                END_USE_CODE
            end on'''

        output = do_compile(code, compact_variables = True)
        self.assertTrue('5' in output)
        self.assertTrue('6' not in output)
        self.assertTrue('7' not in output)
        self.assertTrue('8' in output)

class VariableRedeclaration(unittest.TestCase):
    def testVariableRedeclaration(self):
        code = '''
            function foo
                declare global x
                message(x)
            end function

            on init
                foo
                declare x
            end on'''

        self.assertRaises(ParseException, do_compile, code)

class VariableModifiersTest(unittest.TestCase):
    def testPersistenceModifier(self):
        code = '''
            on init
                declare pers foo := 4
            end on'''

        output = do_compile(code)
        self.assertTrue('declare $foo := 4'     in output)
        self.assertTrue('make_persistent($foo)' in output)

    def testReadPersistenceModifier(self):
        code = '''
            on init
                declare read ui_button bar
            end on'''

        output = do_compile(code)
        self.assertTrue('declare ui_button $bar'    in output)
        self.assertTrue('make_persistent($bar)'     in output)
        self.assertTrue('read_persistent_var($bar)' in output)

class ConstBlockTests(unittest.TestCase):
    def testConstBlock(self):
        code = '''
            on init
                const VARS
                    foo := 0
                    bar := 1
                end const
            end on'''

        output = do_compile(code)
        self.assertTrue('declare %VARS[2] := (0, 1)'     in output)
        self.assertTrue('declare const $VARS__SIZE := 2' in output)
        self.assertTrue('declare const $VARS__foo := 0'  in output)
        self.assertTrue('declare const $VARS__bar := 1'  in output)

class Family(unittest.TestCase):
    def testFamily(self):
        code = '''
            on init
                family myfamily
                  declare x
                end family
            end on'''

        output = do_compile(code)
        self.assertTrue('declare $myfamily__x' in output)

    def testNestedFamily(self):
        code = '''
            on init
                family myfamily
                  family mysubfamily
                    declare x
                  end family
                end family
            end on'''

        output = do_compile(code)
        self.assertTrue('declare $myfamily__mysubfamily__x' in output)

class AutomaticAddingOfParenthesis(unittest.TestCase):
    def testIfParenthesis(self):
        code = '''
            on init
                if 10*2=20
                end if
            end on'''

        output = do_compile(code)
        self.assertTrue('if (10*2=20)' in output)

    def testWhileParenthesis(self):
        code = '''
            on init
                while 10*2=20
                end while
            end on'''

        output = do_compile(code)
        self.assertTrue('while (10*2=20)' in output)

    def testSelectParenthesis(self):
        code = '''
            on init
                declare x
                select x
                  case 5
                    message("here")
                end select
            end on'''

        output = do_compile(code)
        self.assertTrue('select ($x)' in output)

class ForLoop(unittest.TestCase):
    def testForLoopBasic(self):
        code = '''
            on init
                declare i
                for i := 0 to 10
                  message(i)
                end for
            end on'''

        expected_output = '''
            on init
            declare $i
            $i := 0
            while ($i<=10)
            message($i)
            inc($i)
            end while
            end on'''

        output = do_compile(code, remove_preprocessor_vars = True)
        assert_equal(self, output, expected_output)

    def testForLoopBasicDown(self):
        code = '''
            on init
                declare i
                for i := 10 downto 0
                  message(i)
                end for
            end on'''

        expected_output = '''
            on init
            declare $i
            $i := 10
            while ($i>=0)
            message($i)
            dec($i)
            end while
            end on'''

        output = do_compile(code, remove_preprocessor_vars = True)
        assert_equal(self, output, expected_output)

    def testForLoopStep(self):
        code = '''
            on init
                declare i
                for i := 0 to 10 step 2
                  message(i)
                end for
            end on'''

        expected_output = '''
            on init
            declare $i
            $i := 0
            while ($i<=10)
            message($i)
            $i := $i+2
            end while
            end on'''

        output = do_compile(code, remove_preprocessor_vars = True)
        assert_equal(self, output, expected_output)

    def testOptimizationWhenLastValueContainsMinusOne(self):
        code = '''
            on init
                declare i
                for i := 0 to NUM_GROUPS-1
                end for
            end on'''

        expected_output = '''
            on init
            declare $i
            $i := 0
            while ($i<$NUM_GROUPS)
            inc($i)
            end while
            end on'''

        output = do_compile(code, remove_preprocessor_vars = True)
        assert_equal(self, output, expected_output)

class IfElse(unittest.TestCase):
    def testIfElse(self):
        code = '''
            on init
                if NUM_GROUPS<10
                    message("very few groups")
                else if NUM_GROUPS<20
                    message("quite few groups")
                else
                    message("lots of groups")
                end if
            end on'''

        expected_output = '''
            on init
            if ($NUM_GROUPS<10)
            message("very few groups")
            else
            if ($NUM_GROUPS<20)
            message("quite few groups")
            else
            message("lots of groups")
            end if
            end if
            end on'''

        output = do_compile(code, remove_preprocessor_vars = True)
        assert_equal(self, output, expected_output)

class CompactOutput(unittest.TestCase):
    def testCompactOutput(self):
        code = '''
            on init
                declare myVar
                message(myVar)
            end on'''

        output = do_compile(code, compact_variables = True)
        self.assertTrue('declare $najav' in output)
        self.assertTrue('message($najav)' in output)

    def testCompactOutputPrefixesTakenIntoAccount(self):
        # if the variables have different prefixes they shouldn't create a clash after compacting
        code = '''
            on init
                declare $var
                declare %var[10]
            end on'''

        do_compile(code, compact_variables = True)

class VariableDeclarationCheck(unittest.TestCase):
    def testVariableDeclaredOutsideInit(self):
        code = '''
            on note
                declare x := 5
            end on
            '''

        self.assertRaises(ParseException, do_compile, code)

    def testVariableIntDeclaration(self):
        code = '''
            on init
                declare x := 5
            end on
            '''

        output = do_compile(code)
        self.assertTrue('declare $x := 5' in output)

    def testVariableRealDeclaration(self):
        code = '''
            on init
                declare ~x := 5.0
            end on
            '''

        output = do_compile(code)
        self.assertTrue('declare ~x := 5.0' in output)

    def testVariableStringDeclaration(self):
        code = '''
            on init
                declare @s := "test"
            end on
            '''

        output = do_compile(code)
        self.assertTrue('declare @s' in output)
        self.assertTrue('@s := "test"' in output)

    def testVariableIntArrayDeclaration(self):
        code = '''
            on init
                declare int_array[10] := (0)
            end on
            '''

        output = do_compile(code)
        self.assertTrue('declare %int_array[10] := (0)' in output)

    def testVariableRealArrayDeclaration(self):
        code = '''
            on init
                declare ?real_array[10] := (0.0)
            end on
            '''

        output = do_compile(code)
        self.assertTrue('declare ?real_array[10] := (0.0)' in output)

    def testVariableStringArrayDeclaration(self):
        code = '''
            on init
                declare !string_array[5] := ("a", "b", "c", "d", "e")
            end on
            '''

        expected_output = '''on init
            declare !string_array[5]
            !string_array[0] := "a"
            !string_array[1] := "b"
            !string_array[2] := "c"
            !string_array[3] := "d"
            !string_array[4] := "e"
            end on'''

        output = do_compile(code, remove_preprocessor_vars = True)
        assert_equal(self, output, expected_output)

class LocalVariableCheck(unittest.TestCase):
    def testLocalVariableDeclaration(self):
        # make sure that each local variable is separate from other with the same name in other functions

        code = '''
            function foo
              declare x
              message(x+1)
            end function

            function bar
              declare x
              message(x+2)
            end function

            on init
              declare x
              foo
              bar
            end on'''

        output = do_compile(code)
        self.assertTrue('message($_x+1)'  in output)
        self.assertTrue('message($_x2+2)' in output)

    def testLocalVariableDeclaration2(self):
        # make sure that each local variable is separate from other with the same name in other functions

        code = '''
            function foo
              declare const X := 1
              message(X*2)
              bar
            end function

            function bar
              declare const X := 2
              message(X*2)
            end function

            on init
              declare const X := 0
              message(X*2)
              foo
            end on'''

        expected_output = '''
            on init
            message(0)
            message(2)
            message(4)
            end on'''

        output = do_compile(code, optimize = True)
        assert_equal(self, output, expected_output)

    def testLocalVariableDeclaration3(self):
        code = '''
            function foo
              declare myarray[5] := (1, 2, 3, 4, 5)
              message(myarray[0])
            end function

            on init
              foo
            end on'''

        output = do_compile(code)
        self.assertTrue('declare %_myarray[5] := (1, 2, 3, 4, 5)' in output)
        self.assertTrue('message(%_myarray[0])' in output)
        self.assertTrue(output.count('(1, 2, 3, 4, 5)') == 1)

    def testLocalVariableUsedInSubscript(self):
        code = '''
            on init
              message('')
              no_work
            end on { init }

            function no_work
              declare n
              declare x[10]

              for n := 0 to 9
                message(x[n])   { the local variable n is used within a subscript, ensure that it's handled correctly }
              end for
            end function
            '''

        output = do_compile(code)
        self.assertTrue('message(%_x[$_n])' in output)

class UIArrayCheck(unittest.TestCase):
    def testUIArrayDeclaration(self):
        code = '''
            on init
                declare ui_slider volumeSliders[3] (0, 100)
            end on'''

        expected_output = '''
            on init
              declare $concat_it
              declare $concat_offset
              declare $string_it
              declare $list_it
              declare $preproc_i
              declare %volumeSliders[3]
              declare ui_slider $volumeSliders0(0,100)
              declare ui_slider $volumeSliders1(0,100)
              declare ui_slider $volumeSliders2(0,100)
              $preproc_i := 0
              while ($preproc_i<=2)
                %volumeSliders[$preproc_i] := get_ui_id($volumeSliders0)+$preproc_i
                inc($preproc_i)
              end while
            end on'''

        output = do_compile(code)
        assert_equal(self, output, expected_output)

class GlobalVariableCheck(unittest.TestCase):
    def testGlobalVariableDeclaration(self):
        code = '''
            function foo
              declare global x
            end function

            function bar
              message(x+1)
            end function

            on note
              bar
              foo
            end on'''

        output = do_compile(code)
        self.assertTrue('message($x+1)' in output)

class LocalKeywordCheck(unittest.TestCase):
    def testLocalKeyword(self):
        # verify that the automatic global modifier in functions with 'on_init' in their name
        # can be overriden by using "declare local ..."

        code = '''
            function on_init_foo
              declare local x
              message(x+1)
            end function

            on init
              declare x
              on_init_foo
            end on'''

        output = do_compile(code)
        self.assertTrue('message($_x+1)' in output)

class AutomaticVariablePrefixing(unittest.TestCase):
    def testAutomaticPrefixes(self):
        code = '''
            on init
                declare a
                declare b[10]
            end on'''

        output = do_compile(code)
        self.assertTrue('$a' in output)
        self.assertTrue('%b' in output)

    def testNonAmbigiousPrefix(self):
        code = '''
            on init
                declare var
                declare var[10]
                message(var[1])
            end on'''

        output = do_compile(code)
        self.assertTrue('message(%var[1])' in output)

    def testAmbigiousPrefix(self):
        code = '''
            on init
                declare var
                declare var[10]
                message(var)
            end on'''

        self.assertRaises(ParseException, do_compile, code)

class HexNumberCheck(unittest.TestCase):
    def testExtendedSyntax(self): #0x12f
        code = '''
            on init
              message(0x12f)
            end on'''

        output = do_compile(code)
        self.assertTrue('message(303)' in output)

    def testStandardSyntax(self):
        code = '''
            on init
              message(012fh)
            end on'''

        output = do_compile(code)
        self.assertTrue('message(303)' in output)

class TypeChecks(unittest.TestCase):
    def testAssignStringToIntVar1(self):
        code = '''
            on init
                declare x := 'test'
            end on'''

        self.assertRaises(ParseException, do_compile, code, extra_syntax_checks=True)

    def testAssignStringToIntVar2(self):
        code = '''
            on init
                declare x
                x := 'test'
            end on'''

        self.assertRaises(ParseException, do_compile, code)

    def testAssignIntToStringVar(self):
        code = '''
            on init
                declare @x
                x := 5
            end on'''

        do_compile(code)  # make sure this doesn't throw an exception

    def testAssignArrayToIntVar1(self):
        code = '''
            on init
                declare myarray[10]
                declare x := myarray
            end on'''

        self.assertRaises(ParseException, do_compile, code)

    def testAssignArrayToIntVar2(self):
        code = '''
            on init
                declare myarray[10]
                declare x
                x := myarray
            end on'''

        self.assertRaises(ParseException, do_compile, code)

    def testAssignStringArrayToIntVar1(self):
        code = '''
            on init
                declare !myarray[10]
                declare x := myarray
            end on'''

        self.assertRaises(ParseException, do_compile, code)

    def testAssignStringArrayToIntVar2(self):
        code = '''
            on init
                declare !myarray[10]
                declare x
                x := myarray
            end on'''

        self.assertRaises(ParseException, do_compile, code)

    def testAddIntAndString(self):
        code = '''
            on init
                declare @mystring
                declare x
                message(x + mystring)
            end on'''

        self.assertRaises(ParseException, do_compile, code)

    def testConcatenateIntAndString(self):
        code = '''
            on init
                declare @mystring
                declare x
                message(x & mystring)
            end on'''

        do_compile(code)

    def testParameterTypeForBuiltinFunction(self):
        code = '''
            on init
                declare x
                message(num_elements(x))
            end on'''

        self.assertRaises(ParseException, do_compile, code)

    def testParametersWithDifferentTypesToMessage(self):
        code = '''
            on init
                message(1)
                message('test string')
            end on'''

        do_compile(code)

    def testLogicOperatorWithIntOperand(self):
        code = '''
            on init
                declare x
                if not x
                   { ... }
                end if
            end on'''

        self.assertRaises(ParseException, do_compile, code)

    def testUseBuiltinConstantsAsVarRefs(self):
        code = '''
            on init
                set_engine_par(ENGINE_PAR_STEREO, 500000, -1, 4, NI_BUS_OFFSET + 5)
            end on'''

        expected_output = '''
            on init
            set_engine_par($ENGINE_PAR_STEREO,500000,-1,4,$NI_BUS_OFFSET+5)
            end on'''

        output = do_compile(code, optimize = True)
        assert_equal(self, output, expected_output)

class MacroDefineChecks(unittest.TestCase):
    def testBasicMacroDefine(self):
        code = '''
            define TEST := 5
            on init
                message(TEST)
            end on
            '''

        output = do_compile(code)
        self.assertTrue('message(5)' in output)

    def testMacroDefineInString(self):
        code = '''
            define MYDEFINE := 5
            on init
                message("MYDEFINE")
            end on
            '''

        output = do_compile(code)
        self.assertTrue('message("MYDEFINE")' in output)

class MacroOverloading(unittest.TestCase):
    def testOverloadedWithNumArgs(self):
        code = '''
            on init
                test_macro()
                test_macro(a)
                test_macro(a,b,c)
            end on
            macro test_macro
                message("macro with 0 arguments")
            end macro
            macro test_macro(#name#)
                message("macro with 1 argument")
            end macro
            macro test_macro(#name#, #x#, #y#)
                message("macro with 3 arguments")
            end macro
            '''

        output = do_compile(code)
        self.assertTrue('message("macro with 0 arguments")' in output)
        self.assertTrue('message("macro with 1 argument")' in output)
        self.assertTrue('message("macro with 3 arguments")' in output)

    def testOverloadedNestedWithNumArgs(self):
        code = '''
            on init
                test_macro()
            end on
            macro test_macro
                message("macro with 0 arguments")
                test_macro(a,b,c)
            end macro
            macro test_macro(#name#, #x#, #y#)
                message("macro with 3 arguments")
            end macro'''

        output = do_compile(code)
        self.assertTrue('message("macro with 0 arguments")' in output)
        self.assertTrue('message("macro with 3 arguments")' in output)

class MacroInlining(unittest.TestCase):
    def testBasicMacroInlining(self):
        code = '''
            macro foo(x)
              message(x*5)
            end macro

            on init
                foo(10+1)
            end on'''

        output = do_compile(code, remove_preprocessor_vars = False)
        # parenthesis is not added around the 10+1 like it would have been if foo had been a function
        self.assertTrue('message(10+1*5)'   in output or
                        'message(10+(1*5))' in output)

    def testBasicMacroInliningPartOfParameterName(self):
        code = '''
            macro declare_label(#x#)
              declare ui_label lb_#x#(1,1)
            end macro

            on init
                declare_label(mylabel)
            end on'''

        output = do_compile(code)
        self.assertTrue('declare ui_label $lb_mylabel(1,' in output)

    def testBasicMacroInliningPartOfParameterNameInsideString(self):
        code = '''
            macro show_value(#x#)
              message('the value of #x# is: ' & #x#)
            end macro

            on init
                declare y := 5
                show_value(y)
            end on'''

        output = do_compile(code, remove_preprocessor_vars = False)
        self.assertTrue('''message("the value of y is: " & $y)''' in output)

    def testMacroExpansionWithDefineInExpandedString(self):
        code = '''
            define MYDEFINE := 5

            macro test(#string#)
                message("#string#, keeping MYDEFINE unreplaced")
            end macro

            on init
                test(Hello)
            end on'''

        output = do_compile(code)
        self.assertTrue('message("Hello, keeping MYDEFINE unreplaced")' in output)

    def testInfiniteMacroRecursion(self):
        code = '''
            macro foo(x)
              bar(x+1)
            end macro

            macro bar(y)
              foo(y*5)
            end macro

            on init
                foo(1+2)
            end on'''

        self.assertRaises(ParseException, do_compile, code)

    def testWrongNumberOfParameters(self):
        code = '''
            macro foo(x)
              message(x)
            end macro

            on init
                foo(1, 2)
            end on'''

        self.assertRaises(ParseException, do_compile, code)

class MacroIterChecks(unittest.TestCase):
    def testMacrosIterate(self):
        code = '''
            on init
                iterate_macro(foo) := 0 to 3
            end on

            macro foo(#n#)
                declare var_#n# := #n#
            end macro'''

        output = do_compile(code)
        self.assertTrue('declare $var_0' in output)
        self.assertTrue('declare $var_1' in output)
        self.assertTrue('declare $var_2' in output)
        self.assertTrue('declare $var_3' in output)

    def testMacrosLiterate(self):
        code = '''
            on init
                literate_macro(foo) on banana, pineapple, kiwi
            end on

            macro foo(#g#)
                declare #g#
            end macro'''

        output = do_compile(code)
        self.assertTrue('declare $banana' in output)
        self.assertTrue('declare $pineapple' in output)
        self.assertTrue('declare $kiwi' in output)

    def testPostIterateMacro(self):
        code = '''
            on init
                iterate_post_macro(declare ui_button mySwitch_#n#) := 0 to 3
            end on'''

        output = do_compile(code)
        self.assertTrue('declare ui_button $mySwitch_0' in output)
        self.assertTrue('declare ui_button $mySwitch_1' in output)
        self.assertTrue('declare ui_button $mySwitch_2' in output)
        self.assertTrue('declare ui_button $mySwitch_3' in output)

    def testDefinesInIterateMacros(self):
        code = '''
            on init
                define NUM_MENUS := 3
                declare ui_menu menus[NUM_MENUS]
                iterate_macro(add_menu_item(menus#n#, "Item", 0)) := 0 to NUM_MENUS - 1
            end on'''

        expected_output = '''
            on init
              declare $concat_it
              declare $concat_offset
              declare $string_it
              declare $list_it
              declare $preproc_i
              declare %menus[3]
              declare ui_menu $menus0
              declare ui_menu $menus1
              declare ui_menu $menus2
              $preproc_i := 0
              while ($preproc_i<=2)
                %menus[$preproc_i] := get_ui_id($menus0)+$preproc_i
                inc($preproc_i)
              end while
              add_menu_item($menus0,"Item",0)
              add_menu_item($menus1,"Item",0)
              add_menu_item($menus2,"Item",0)
            end on'''

        output = do_compile(code)
        assert_equal(self, output, expected_output)

class LineContinuation(unittest.TestCase):
    def testMacrosInvokingEachOtherNotSupported(self):
        code = '''
            on init
                declare x
                message('this is a really long line ... ' & ...
                        'so it is broken up into multiple lines. x=' & ...
                        x)
            end on'''

        output = do_compile(code)
        self.assertTrue('''message("this is a really long line ... " & "so it is broken up into multiple lines. x=" & $x)''' in output)

class FunctionInlining(unittest.TestCase):
    def testBasicInlining(self):
        code = '''
            function foo(x)
              bar(x+1)
            end function

            function bar(y)
              message(y*5)
            end function

            on init
                foo(10)
            end on'''

        output = do_compile(code)
        self.assertTrue('message((10+1)*5)' in output)

    def testDoubleSubscriptAfterInlining(self):
        code = '''
            function foo(x)
              message(x[5]
            end function

            on init
              declare mylist[10]
              foo(mylist[2])
            end on'''

        self.assertRaises(ParseException, do_compile, code)

    def testRecursion(self):
        code = '''
            function foo(x)
              bar(x)
            end function

            function bar(y)
              foo(x)
            end function

            on init
                foo(10)
            end on'''

        self.assertRaises(ParseException, do_compile, code)

    def testWrongNumberOfParameters(self):
        code = '''
            function foo(x)
              message(x)
            end function

            on init
                foo(1, 2)
            end on'''

        self.assertRaises(ParseException, do_compile, code)

    def testFunctionWithReturnValueOneLiner(self):
        code = '''
            function scale_up(x) -> result
              result := x*100
            end function

            function scale_down(x) -> result
              result := x/100
            end function

            on init
                message(scale_up(5+4))
                message(scale_down(scale_up(1)))
            end on'''

        output = do_compile(code)
        self.assertTrue('message((5+4)*100)' in output)
        self.assertTrue('message(1*100/100)' in output)

    def testFunctionWithReturnValueOneLinerWithoutParams(self):
        code = '''
            function last_group_index -> result
              result := NUM_GROUPS-1
            end function

            on init
                message(last_group_index())    { for this type of function one has to use () after the function name }
            end on'''

        output = do_compile(code)
        self.assertTrue('message($NUM_GROUPS-1)' in output)

    def testFunctionWithReturnValueMultiLiner(self):
        code = '''
            function scale_up(x) -> result
              result := x*10
              result := result*10
            end function

            on init
                declare x
                x := scale_up(5)
            end on'''

        output = do_compile(code)
        self.assertTrue('$x := 5*10' in output)
        self.assertTrue('$x := $x*10' in output)

    def testFunctionWithReturnValueInProperUse(self):
        code = '''
            function scale_up(x) -> result
              message(x)
              result := x*100
            end function

            on init
                message(scale_up(5+4))    { scale_up needs to be a one-liner when invoked like this }
            end on'''

        self.assertRaises(ParseException, do_compile, code)

    def testFamilyPassedAsParameter(self):
        code = '''
            function setxmember(fam, value)
              fam.x := value
            end function

            on init
                family myfamily
                    declare x
                end family
                setxmember(myfamily, 5)
            end on'''

        output = do_compile(code)
        self.assertTrue('$myfamily__x := 5' in output)

    def testNestedFamilyPassedAsParameter(self):
        code = '''
            function setxmember(fam, value)
              fam.x := value
            end function

            on init
                family fam1
                    family fam2
                        declare x
                    end family
                end family
                setxmember(fam1.fam2, 5)
            end on'''

        output = do_compile(code)
        self.assertTrue('$fam1__fam2__x := 5' in output)

    def testFunctionRedeclaration(self):
        code = '''
            function foo
            end function

            function foo
            end function

            on init
                foo
            end on'''

        self.assertRaises(ParseException, do_compile, code)

    def testFunctionWithSameNameAsParameter(self):
        code = '''
            function foo(foo)
              message(foo)
            end function

            on init
                foo(5)    { only the parameter should be replaced by 5, not the function name }
            end on'''

        output = do_compile(code)
        self.assertTrue('message(5)' in output)

    def testSubstitutionOfBothArrayNameAndIndex(self):
        code = '''
            function set_value_at(array, index, value)
              array[index] := value
            end function

            on init
              declare my_array[100]
              set_value_at(my_array, 0, 10)
            end on'''

        output = do_compile(code)
        self.assertTrue('%my_array[0] := 10' in output)

class FunctionInvocationUsingCall(unittest.TestCase):
    def testNotAllowedInOnInit(self):
        code = '''
            function foo
              message(5)
            end function

            on init
                call foo
            end on'''

        self.assertRaises(ParseException, do_compile, code)

    def testCallFunctionWithParameters(self):
        code = '''
            function foo(x)
              message(x)
            end function

            on init
                call foo(5)
            end on'''

        self.assertRaises(ParseException, do_compile, code)

    def testCallFunctionWithReturnValue(self):
        code = '''
            function foo -> result
              result := 5
            end function

            on init
                call foo
            end on'''

        self.assertRaises(ParseException, do_compile, code)

    def testWrongNumberOfParameters(self):
        code = '''
            function foo(x)
              message(x)
            end function

            on init
                foo(1, 2)
            end on'''

        self.assertRaises(ParseException, do_compile, code)

    def testRecursion(self):
        code = '''
            function foo(x)
              bar(x)
            end function

            function bar(y)
              foo(x)
            end function

            on init
                foo(10)
            end on'''

        self.assertRaises(ParseException, do_compile, code)

    def testTopologicalSortOfFunctionDefs(self):
        code = '''
            function foo
              call bar
            end function

            function bar
              message('in bar function')
            end function

            on note
                call foo
            end on'''

        output = do_compile(code)
        self.assertTrue(output.index('function bar') < output.index('function foo'), 'Functions should be reordered so that they are always defined before they are used')

class NamespacePrefixing(unittest.TestCase):
    def testNamespacePrefixing(self):
        code = '''
            import 'test_imports/namespace1.ksp' as mymodule

            on init
                declare x := 10
                declare y := 5
                mymodule.sort_ascendingly(x, y)
            end on'''

        output = do_compile(code, optimize = True)
        self.assertTrue('_mymodule__tmp' in output)

    def testFunctionReturnValuesNotPrefixed(self):
        code = '''
            import 'test_imports/namespace2.ksp' as mymodule

            on init
                declare x
                x := mymodule.max(8, 3)
            end on'''

        output = do_compile(code, optimize = True)
        self.assertTrue('x := 8' in output)

    def testMacroImportedPrefixed(self):
        code = '''
            import 'test_imports/namespace3.ksp' as mymodule

            on init
                mymodule.declare_var(variable)
            end on'''

        output = do_compile(code)
        self.assertTrue('declare $mymodule__variable' in output)

    def testOverloadedMacroImportedPrefixed(self):
        code = '''
            import 'test_imports/namespace4.ksp' as mymodule

            on init
                mymodule.foo
                mymodule.foo(0, 0)
            end on'''

        output = do_compile(code)
        self.assertTrue('message("macro with no arguments")' in output)
        self.assertTrue('message("macro with 2 arguments")' in output)

class PragmaTests(unittest.TestCase):
    def testPragma(self):
        code = '''
            import 'test_imports/pragma.ksp' as mymodule
            { #pragma preserve_names X, Y }

            on init
                declare X
                declare Y
                declare Z
                mymodule.declare_variables
            end on'''

        output = do_compile(code, remove_preprocessor_vars = True, compact_variables = True)
        self.assertTrue('declare $mymodule__K' in output)
        self.assertTrue('declare $X' in output)
        self.assertTrue('declare $Y' in output)
        self.assertTrue('declare $Z' not in output)

class OptimizationModeChecks(unittest.TestCase):
    def testBasicArithmeticExpression(self):
        code = '''
            on init
                declare const FACTOR := 5
                message(FACTOR * (3 + 7))
            end on'''

        output = do_compile(code, optimize = True)
        self.assertTrue('message(50)' in output)

    def testNegativeDivisionTruncation(self):
        code = '''
            on init
                message(-10/9)
            end on'''

        output = do_compile(code, optimize = True)
        self.assertTrue('message(-1)' in output)

    def testModulo(self):
        code = '''
            on init
                message(11 mod 5)
                message(-12 mod 5)
                message(13 mod -5)
                message(-14 mod -5)
            end on'''

        output = do_compile(code, optimize = True)
        self.assertTrue('message(1)' in output)
        self.assertTrue('message(-2)' in output)
        self.assertTrue('message(3)' in output)
        self.assertTrue('message(-4)' in output)

    def testOverflow(self):
        code = '''
            on init
                message(5555555 * 555555)
            end on'''

        output = do_compile(code, optimize = True)
        self.assertTrue('message(-1665127799)' in output)

    def testRemoveUnusedVariablesAndFunctions(self):
        code = '''
            function funcA
              call funcB
            end function

            function funcB
              declare x
              message(1)
            end function

            on note
                if 1 = 0
                  call funcA
                end if
            end on'''

        output = do_compile(code, optimize = True)
        self.assertTrue('declare' not in output)
        self.assertTrue('call' not in output)
        self.assertTrue('func' not in output)

    def testRemoveUnusedVariablesAndFunctions2(self):
        code = '''
            on note
              two_way
            end on

            function two_way
              if 2 > 1
                call fn1
              else
                call fn2
              end if
            end function

            function fn1
              declare global abc
              abc := 72
            end function

            function fn2
              declare global xyz
              xyz := 55
            end function'''

        output = do_compile(code, optimize = True)
        self.assertTrue('declare $abc' in output)
        self.assertTrue('declare $xyz' not in output)
        self.assertTrue('fn2' not in output)

    def testBinaryExpressions1(self):
        code = '''
            on init
                declare x
                if 1 # 0 or x = 9
                    message('test')
                end if
            end on'''

        output = do_compile(code, optimize = True)
        self.assertTrue('2 # 0' not in output)

    def testBinaryExpressions2(self):
        code = '''
            on init
                declare x
                if 1 = 0 and x = 9
                    message('test')
                end if
            end on'''

        output = do_compile(code, optimize = True)
        self.assertTrue('message' not in output)

    def testBinaryExpressions3(self):
        code = '''
            on init
                declare x
                message(0*x)
            end on'''

        output = do_compile(code, optimize = True)
        self.assertTrue('message(0)' in output)

    def testBinaryExpressions4(self):
        code = '''
            on init
                declare x
                message(x*1)
            end on'''

        output = do_compile(code, optimize = True)
        self.assertTrue('message($x)' in output)

    def testBinaryExpressions5(self):
        code = '''
            on init
                declare x
                message(0+x)
            end on'''

        output = do_compile(code, optimize = True)
        self.assertTrue('message($x)' in output)

    def testIfOneEqualsOne(self):
        code = '''
            on init
                if 1=1
                    message("test1")
                end if
                if 2=2
                    message("test2")
                end if
            end on'''

        output = do_compile(code, optimize = True)
        self.assertTrue('if (1=1)' in output)
        self.assertTrue('2=2' not in output)

class PropertyTests(unittest.TestCase):
    def testAlias1(self):
        code = '''
            on init
              declare a
              property b -> a
              message(b)
            end on'''

        output = do_compile(code)
        self.assertTrue('message($a)' in output)

    def testAlias2(self):
        code = '''
            on init
              declare _list[100]
              property list[a,b] -> _list[a*10+b]
              list[3,5] := 99
            end on'''

        output = do_compile(code, optimize = True)
        self.assertTrue('%_list[35] := 99' in output)

    def testPropertyWithMultilineGet(self):
        code = '''
            on init
                property has_many_groups
                    function get() -> result
                        if NUM_GROUPS > 100
                            result := 1
                        else
                            result := 0
                        end if
                    end function
                end property
                declare x
                x := has_many_groups
            end on'''

        output = do_compile(code)
        self.assertTrue('if ($NUM_GROUPS' in output)

    def testPropertyWithoutIndex(self):
        code = '''
            on init
                declare _data
                property myprop

                  function get() -> result
                    result := _data*_data
                  end function

                  function set(value)
                    _data := value
                  end function

                end property

                myprop := 1
                message(myprop)
                test(myprop)
            end on

            function test(prop)
              prop := 2
            end function
            '''

        output = do_compile(code)
        self.assertTrue('$_data := 1' in output)
        self.assertTrue('message($_data*$_data)' in output)
        self.assertTrue('$_data := 2' in output)

    def testPropertyUsingMacro(self):
        code = '''
            macro GET(expression)
              function get() -> result
                result := expression
              end function
            end macro
            macro SET(lhs)
              function set(value)
                lhs := value
              end function
            end macro

            on init
                declare _data
                property myprop
                  GET(_data*_data)
                  SET(_data)
                end property

                myprop := 1
                message(myprop)
            end on'''

        output = do_compile(code)
        self.assertTrue('$_data := 1' in output)
        self.assertTrue('message($_data*$_data)' in output)

    def testPropertyUsingMacro2(self):
        code = '''
            macro add_engine_par(#prop#, engine_par)
                property group.slot.generic.#prop#
                    function get(group, slot, generic) -> result
                        result := get_engine_par(engine_par, group, slot, generic)
                    end function

                    function set(group, slot, generic, value)
                        set_engine_par(engine_par, value, group, slot, generic)
                    end function
                end property

                property group.slot.generic.#prop#.disp
                    function get(group, slot, generic) -> result
                        result := get_engine_par_disp(engine_par, group, slot, generic)
                    end function
                end property
            end macro

            on init
                add_engine_par(volume, ENGINE_PAR_VOLUME)
                declare ui_slider Vol (0, 1000000)
                Vol := group[-1].slot[-1].generic[-1].volume
            end on'''

        output = do_compile(code)
        self.assertTrue('$Vol := get_engine_par($ENGINE_PAR_VOLUME,-1,-1,-1)' in output)

    def testPropertyWithinFamily(self):
        code = '''
            function on_init_func
                declare _data
                family myfamily
                    property myprop

                      function get() -> result
                        result := _data*_data
                      end function

                      function set(value)
                        _data := value
                      end function

                    end property
                end family
            end function

            on init
                on_init_func
                myfamily.myprop := 1
                message(myfamily.myprop)
                test(myfamily.myprop)
            end on

            function test(prop)
              prop := 2
            end function
            '''

        output = do_compile(code)
        self.assertTrue('$_data := 1' in output)
        self.assertTrue('message($_data*$_data)' in output)
        self.assertTrue('$_data := 2' in output)

    def testPropertyWithIndex(self):
        code = '''
            on init
                declare _data[10]
                property myprop

                  function get(index) -> result
                    result := _data[index]
                  end function

                  function set(index, value)
                    _data[index] := value
                  end function

                end property

                myprop[1] := 1
                message(myprop[3])
                test(myprop)
            end on

            function test(prop)
              prop[0] := 2
            end function
            '''

        output = do_compile(code)
        self.assertTrue('%_data[1] := 1' in output)
        self.assertTrue('message(%_data[3])' in output)
        self.assertTrue('%_data[0] := 2' in output)

class FunctionAsArgumentTest(unittest.TestCase):
    def testFunctionAsArgument(self):
        code = '''
            on init
                execute(show_value)
            end on

            function execute(func)
              func(5)
            end function

            function show_value(x)
              message(x)
            end function
            '''

        output = do_compile(code)
        self.assertTrue('message(5)' in output)

    def testParameterlessFunctionAsArgument(self):
        code = '''
            on init
                execute(show_value)
            end on

            function execute(func)
              func
            end function

            function show_value
              message(5)
            end function
            '''

        output = do_compile(code)
        self.assertTrue('message(5)' in output)

    def testCalledFunctionAsArgument(self):
        code = '''
            on note
                execute(show_value)
            end on

            function execute(func)
              call func
            end function

            function show_value
              message(5)
            end function
            '''

        output = do_compile(code)
        self.assertTrue('function show_value' in output)
        self.assertTrue('message(5)' in output)

class ControlParTest(unittest.TestCase):
    def testGetUiIDWrapping(self):
        # ensure that get_ui_id is added:

        code = '''
            on init
                declare ui_knob myknob(0, 100, 1)
                set_control_par(myknob, CONTROL_PAR_POS_X, 100)
            end on'''

        output = do_compile(code)
        self.assertTrue('set_control_par(get_ui_id($myknob),$CONTROL_PAR_POS_X,100)' in output)

    def testControlPar(self):
        code = '''
            on init
                family myfam
                  declare ui_knob myknob (0, 100, 1)
                end family

                make_settings(myfam)

                declare ui_value_edit myvalue (0, 100, 1)
                declare control_reference
                control_reference := get_ui_id(myvalue)
                control_reference->value := 10
                CONTROL_REFERENCE->value := 10   { test case-sensitivity }

                declare ui_label Engine.label (1, 1)
                declare ui_knob  Engine.knob (0, 128, 1)
                declare ui_panel Engine.panel
                Engine.label -> picture_state := Engine.knob
                Engine.label -> parent_panel := Engine.panel

                declare ui_button A[5]
                declare ui_panel Panel[2]

                A0 -> parent_panel := Panel0
            end on

            function make_settings(fam)
              fam.myknob->x := 10
              fam.myknob->text := 'text'
              message(fam.myknob->x)
              message(fam.myknob->text)
            end function'''

        output = do_compile(code)

        # get_ui_id should automatically be inserted on these lines:
        self.assertTrue('set_control_par(get_ui_id($myfam__myknob),$CONTROL_PAR_POS_X,10)' in output)
        self.assertTrue('set_control_par_str(get_ui_id($myfam__myknob),$CONTROL_PAR_TEXT,"text")' in output)
        self.assertTrue('message(get_control_par(get_ui_id($myfam__myknob),$CONTROL_PAR_POS_X))' in output)
        self.assertTrue('message(get_control_par_str(get_ui_id($myfam__myknob),$CONTROL_PAR_TEXT))' in output)
        self.assertTrue('set_control_par(get_ui_id($Engine__label),$CONTROL_PAR_PARENT_PANEL,get_ui_id($Engine__panel))' in output)
        self.assertTrue('set_control_par(get_ui_id($A0),$CONTROL_PAR_PARENT_PANEL,get_ui_id($Panel0))' in output)

        # ... but not on this one (since it uses an integer variable and not a UI variable):
        self.assertTrue('set_control_par($control_reference,$CONTROL_PAR_VALUE,10)' in output)
        self.assertTrue('set_control_par(get_ui_id($Engine__label),$CONTROL_PAR_PICTURE_STATE,$Engine__knob)' in output)

    def testEventPars(self):
        '''Make sure that set_event_par can deal with functions that return a constant in the first param'''

        code = '''
            on init
                declare const GRAIN_BLIP_EVT_STORAGE := 1
                declare const EVENT_STATE.RELEASE := 2
                declare const GRAIN_EVENT_PAR0 := 4
            end on
            on note
                if get_event_par_arr(EVENT_ID, EVENT_PAR_CUSTOM,GRAIN_BLIP_EVT_STORAGE) # 0
                    set_event_par(get_event_par_arr(EVENT_ID, EVENT_PAR_CUSTOM,GRAIN_BLIP_EVT_STORAGE), EVENT_PAR_3, ENGINE_UPTIME) //PROBLEM
                    set_event_par_arr(get_event_par_arr(EVENT_ID, EVENT_PAR_CUSTOM,GRAIN_BLIP_EVT_STORAGE), EVENT_PAR_CUSTOM, EVENT_STATE.RELEASE, GRAIN_EVENT_PAR0)
                end if
            end on'''

        output = do_compile(code)
        self.assertTrue('set_event_par(get_event_par_arr($EVENT_ID,$EVENT_PAR_CUSTOM,$GRAIN_BLIP_EVT_STORAGE),$EVENT_PAR_3,$ENGINE_UPTIME)' in output)
        self.assertTrue('set_event_par_arr(get_event_par_arr($EVENT_ID,$EVENT_PAR_CUSTOM,$GRAIN_BLIP_EVT_STORAGE),$EVENT_PAR_CUSTOM,$EVENT_STATE__RELEASE,$GRAIN_EVENT_PAR0)' in output)

    def testEventParsWithArrowNotation(self):
        code = '''
            on note
                get_event_par_arr(EVENT_ID, EVENT_PAR_CUSTOM,5) -> par_3 := ENGINE_UPTIME
                by_marks(MARK_3) -> volume := random(-100000,0)
            end on'''

        output = do_compile(code)
        self.assertTrue('set_event_par(get_event_par_arr($EVENT_ID,$EVENT_PAR_CUSTOM,5),$EVENT_PAR_3,$ENGINE_UPTIME)' in output)
        self.assertTrue('set_event_par(by_marks($MARK_3),$EVENT_PAR_VOLUME,random(-100000,0))' in output)

class TestSubscripts(unittest.TestCase):
    def testSubscripts1(self):
        code = '''
            on init
              declare data[100]
              property prop
                function get(index1, index2) -> result
                  result := data[index1*10 + index2]
                end function
                function set(index1, index2, value)
                  data[index1*10 + index2] := value
                end function
              end property

              prop[3,4] := 99
              message(prop[3,4])
            end on'''

        output = do_compile(code, optimize = True)
        self.assertTrue('%data[34] := 99' in output)
        self.assertTrue('message(%data[34])' in output)

    def testFamilyWithSubscriptAsParameter(self):
        code = '''
            function show_point(p)
                message(p.x & ', ' & p.y)
            end function

            on init
              family points
                declare x[100]
                declare y[100]
              end family
              show_point(points[4])   { verify that the index can be added here and is propagated to the x, y members }
            end on'''

        output = do_compile(code)
        self.assertTrue('message(%points__x[4] & ", " & %points__y[4])' in output)

    def testTooManySubscripts(self):
        code = '''
            function modify_first_element(array_var)
              array_var[0] := 99
            end function

            on init
              declare x[100]
              modify_first_element(x[0])    { the index is incorrectly added here too }
            end on'''

        self.assertRaises(ParseException, do_compile, code)

class TestTaskfunc(unittest.TestCase):
    def testTaskfunc(self):
        code = '''
            on init
              SET_CONDITION(TCM_DEBUG)
              tcm.init(100)
              declare x
            end on

            taskfunc randomize(min, max) -> result
              declare r := random(min, max)
              result := r
            end taskfunc

            on note
              x := randomize(44, 88)
            end on'''

        expected_output = '''
            on init
            declare %p[32768]
            declare $sp
            $sp := 268
            declare $fp
            $fp := 268
            declare $tx
            declare %tstate__id[326]
            declare %tstate__fs[326]
            $tx := 0
            while ($tx<326)
            %tstate__fs[$tx] := 168+($tx*100)
            inc($tx)
            end while
            $tx := 0
            %tstate__id[0] := -1
            pgs_create_key(TCM_EXCEPTION,5)
            pgs_set_key_val(TCM_EXCEPTION,$CURRENT_SCRIPT_SLOT,0)
            declare $x
            end on
            function check_full
            if ($sp<(%tstate__fs[$tx]+2))
            pgs_set_key_val(TCM_EXCEPTION,$CURRENT_SCRIPT_SLOT,2)
            end if
            end function
            function randomize
            %p[$sp-5] := $fp
            $fp := $sp-5
            $sp := $fp
            call check_full
            %p[$fp+1] := random(%p[$fp+2],%p[$fp+3])
            %p[$fp+4] := %p[$fp+1]
            $sp := $fp
            $fp := %p[$fp]
            $sp := $sp+5
            end function
            on note
            %p[$sp-3] := 44
            %p[$sp-2] := 88
            call randomize
            $x := %p[$sp-1]
            end on'''

        output = do_compile(code, optimize = True)
        assert_equal(self, output, expected_output)

    def testTaskfuncWithAdditionalBranchOptimization(self):
        code = '''
            { pragma compile_with extra_branch_optimization }

            on init
              SET_CONDITION(TCM_DEBUG)
              tcm.init(100)
              declare x
            end on

            taskfunc randomize(min, max) -> result
              declare r := random(min, max)
              result := r
            end taskfunc

            on note
              x := randomize(44, 88)
            end on'''

        expected_output = '''
            on init
            declare %p[32768]
            declare $sp
            $sp := 268
            declare $fp
            $fp := 268
            declare $tx
            declare %tstate__id[326]
            declare %tstate__fs[326]
            $tx := 0
            while ($tx<326)
            %tstate__fs[$tx] := 168+($tx*100)
            inc($tx)
            end while
            $tx := 0
            %tstate__id[0] := -1
            pgs_create_key(TCM_EXCEPTION,5)
            pgs_set_key_val(TCM_EXCEPTION,$CURRENT_SCRIPT_SLOT,0)
            declare $x
            end on
            function check_full
            if ($sp<(%tstate__fs[$tx]+2))
            pgs_set_key_val(TCM_EXCEPTION,$CURRENT_SCRIPT_SLOT,2)
            end if
            end function
            function randomize
            %p[$sp-5] := $fp
            $fp := $sp-5
            $sp := $fp
            call check_full
            %p[$fp+1] := random(%p[$fp+2],%p[$fp+3])
            %p[$fp+4] := %p[$fp+1]
            $sp := $fp
            $fp := %p[$fp]
            $sp := $sp+5
            end function
            on note
            %p[$sp-3] := 44
            %p[$sp-2] := 88
            call randomize
            $x := %p[$sp-1]
            end on'''

        output = do_compile(code, optimize = True)
        assert_equal(self, output, expected_output)

    def testTaskfuncWithTWaitAndOutParam(self):
        code = '''
            on init
              tcm.init(100)
              declare x
            end on

            taskfunc randomize(min, max, out result)
              declare r := random(min, max)
              tcm.wait(1000)
              result := r
            end taskfunc

            on note
              randomize(44, 88, x)
            end on'''

        expected_output = '''
            on init
            declare %p[32768]
            declare $sp
            $sp := 268
            declare $fp
            $fp := 268
            declare $tx
            declare %tstate__id[326]
            declare %tstate__sp[326]
            declare %tstate__fp[326]
            declare %tstate__fs[326]
            $tx := 0
            while ($tx<326)
            %tstate__fs[$tx] := 168+($tx*100)
            inc($tx)
            end while
            $tx := 0
            %tstate__id[0] := -1
            pgs_create_key(TCM_EXCEPTION,5)
            pgs_set_key_val(TCM_EXCEPTION,$CURRENT_SCRIPT_SLOT,0)
            declare $x
            end on
            function _twait
            %p[$sp-2] := search(%tstate__id,0)
            if (%p[$sp-2]=-1)
            pgs_set_key_val(TCM_EXCEPTION,$CURRENT_SCRIPT_SLOT,1)
            else
            %tstate__id[$tx] := $NI_CALLBACK_ID
            %tstate__fp[$tx] := $fp
            %tstate__sp[$tx] := $sp
            $tx := %p[$sp-2]
            %tstate__id[$tx] := -1
            $fp := %tstate__fs[$tx]+100
            %p[$fp-1] := %p[$sp-1]
            $sp := $fp
            wait(%p[$sp-1])
            %tstate__id[$tx] := 0
            $tx := search(%tstate__id,$NI_CALLBACK_ID)
            %tstate__id[$tx] := -1
            $fp := %tstate__fp[$tx]
            $sp := %tstate__sp[$tx]
            end if
            end function
            function randomize
            %p[$sp-5] := $fp
            $fp := $sp-5
            $sp := $fp
            %p[$fp+1] := random(%p[$fp+2],%p[$fp+3])
            %p[$sp-1] := 1000
            call _twait
            %p[$fp+4] := %p[$fp+1]
            $sp := $fp
            $fp := %p[$fp]
            $sp := $sp+5
            end function
            on note
            %p[$sp-3] := 44
            %p[$sp-2] := 88
            call randomize
            $x := %p[$sp-1]
            end on'''

        output = do_compile(code, optimize = True)
        assert_equal(self, output, expected_output)

    def testInliningTaskfuncForbidden(self):
        code = '''
            on init
              tcm.init(100)
              declare x
            end on

            taskfunc randomize(min, max) -> result
              declare r := random(min, max)
              result := r
            end taskfunc

            on note
              x := call randomize(44, 88)  { not allowed, one must not use "call" }
            end on'''

        self.assertRaises(ParseException, do_compile, code, optimize = True)

    def testCallInsideGeneralExpressionsForbidden1(self):
        code = '''
            on init
              tcm.init(100)
              declare x
            end on

            taskfunc randomize(min, max) -> result
              result := random(min, max)
            end taskfunc

            on note
              x := randomize(44, 88) + randomize(44, 88)
            end on'''

        self.assertRaises(ParseException, do_compile, code, optimize = True)

    def testCallInsideGeneralExpressionsForbidden2(self):
        code = '''
            on init
              tcm.init(100)
              declare x
            end on

            taskfunc randomize(min, max) -> result
              result := random(min, max)
            end taskfunc

            on note
              x := randomize(44, 88) + 1
            end on'''

        self.assertRaises(ParseException, do_compile, code, optimize = True)

    def testNestedCallsForbidden1(self):
        code = '''
            on init
              tcm.init(100)
              declare x
            end on

            taskfunc square(x) -> result
              result := x*x
            end taskfunc

            on note
              x := square(square(2))
            end on'''

        self.assertRaises(ParseException, do_compile, code, optimize = True)

class K5_6Features(unittest.TestCase):
    def testDeclaration(self):
        code = '''
            on init
                declare ~x := 1.0e6
                declare ?y[10]
                y[5] := 3.3
            end on'''

        expected_output = '''
            on init
            declare ~x := 1000000.0
            declare ?y[10]
            ?y[5] := 3.3
            end on'''

        output = do_compile(code, remove_preprocessor_vars = True)
        assert_equal(self, output, expected_output)

    def testRealArithmetics(self):
        code = '''
            on init
                declare ~x := 1.1 * 2.2 * NI_MATH_PI
            end on'''

        expected_output = '''
            on init
            declare ~x
            ~x := 1.1*2.2*~NI_MATH_PI
            end on'''

        output = do_compile(code, remove_preprocessor_vars = True)
        assert_equal(self, output, expected_output)

    def testNegativeReal(self):
        code = '''
            on init
                declare ~x := -0.001
                message(x)
            end on'''

        expected_output = '''
            on init
            declare ~x := -0.001
            message(~x)
            end on'''

        output = do_compile(code, remove_preprocessor_vars = True, optimize = True)
        assert_equal(self, output, expected_output)

    def testAssignRealToString(self):
        code = '''
            on init
                declare ~x := 9.9
                declare @y
                y := x
            end on'''

        expected_output = '''
            on init
            declare ~x := 9.9
            declare @y
            @y := ~x
            end on'''

        output = do_compile(code, remove_preprocessor_vars = True)
        assert_equal(self, output, expected_output)

    def testIncorrectlyMixedRealAndInteger(self):
        code = '''
            on init
                declare ~x := 5 * 2.333
                message(~x)
            end on'''

        self.assertRaises(ParseException, do_compile, code, extra_syntax_checks = True, optimize = True)

    def testFunctionWithMultipleArgTypes(self):
        code = '''
            on init
                message(abs(-4.1))
                message(abs(-4))
            end on'''

        expected_output = '''
            on init
            message(abs(-4.1))
            message(abs(-4))
            end on'''

        output = do_compile(code, remove_preprocessor_vars = True)
        assert_equal(self, output, expected_output)

    def testRealArithmeticsOptimization1(self):
        code = '''
            on init
                message(1.1 * 2.2)
            end on'''

        expected_output = '''
            on init
            message(2.42)
            end on'''

        output = do_compile(code, extra_syntax_checks = True, optimize = True)
        assert_equal(self, output, expected_output)

    def testRealArithmeticsOptimization2(self):
        code = '''
            on init
                declare const ~x := 2.5
                message(3.0*~x)
            end on'''

        expected_output = '''
            on init
            message(7.5)
            end on'''

        output = do_compile(code, extra_syntax_checks = True, optimize = True)
        assert_equal(self, output, expected_output)

    def testRealConversionOptimized(self):
        code = '''
            on init
                declare const x := real_to_int(3.7)
                declare const ~y := int_to_real(3)
                message(x)
                message(y)
            end on'''

        expected_output = '''
            on init
            message(3)
            message(3.0)
            end on'''

        output = do_compile(code, extra_syntax_checks = True, optimize = True)
        assert_equal(self, output, expected_output)

if __name__ == '__main__':
    unittest.main()