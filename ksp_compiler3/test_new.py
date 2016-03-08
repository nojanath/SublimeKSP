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

from .ksp_compiler import KSPCompiler

def default_read_file_func(filepath):
    return open(filepath, 'r').read()

def do_compile(code, compact=False, compactVars=False, comments_on_expansion=True, read_file_func=default_read_file_func, extra_syntax_checks=True, optimize=False, check_empty_compound_statements=False):
    def callback(desc, how_much_done):
        print('>', desc)
    #line_map = {}
    compiler = KSPCompiler(code, compact, compactVars, comments_on_expansion, read_file_func=read_file_func, extra_syntax_checks=extra_syntax_checks, optimize=optimize, check_empty_compound_statements=check_empty_compound_statements)
    compiler.compile(callback=callback)
    return compiler.compiled_code.replace('\r', '')

dms_code = '''
function twait(time)
        dms.pause := time
        call t.wait
    end function

    function t.wait    { Inner KN function called by twait }
        declare global dms.pause
        push(search(tstate.id,0)){ Find next available task index }
        if p[sp] = -1 { no more left }
        popx { discard -1 }
        exception_code := 0  { too many threads }
        else { save current tasks state }
        tstate.id[tx] := NI_CALLBACK_ID
        tstate.fp[tx] := fp
        tstate.sp[tx] := sp + 1
        pop(tx)
        { now, initialize new active task state }
        tstate.id[tx] := -1
        fp := (tx + 1)*STACK_SIZE + TASK_0
        sp := fp
        { Its now OK to allow another callback or resume of a callback }
        wait(dms.pause)
        { wait has timed out, awaken original task }
        tstate.id[tx] := 0 { active task can now be released  to the pool }
        tx := (search(tstate.id,NI_CALLBACK_ID))
        tstate.id[tx] := -1 { reactivate pre-wait task }
        fp := tstate.fp[tx]
        sp := tstate.sp[tx]
        end if
    end function

    function push(value)
        dec(sp)
        p[sp] := value
    end function

    function pop(value)
        value := p[sp]
        inc(sp)
    end function

    function popx  { discard top of stack }
        inc(sp)
    end function

    function on_init_DMS
        declare const MEM_SIZE := 0x8000 { memory subsystem size }
        declare const MAX_TASKS := 64  { maximum threads allowed }
        declare const MIN_STATIC_SIZE := 1500  { min size of global data area, 0..(TASK_0-1)}
        declare const STACK_SIZE := (MEM_SIZE - MIN_STATIC_SIZE)/MAX_TASKS
        declare const TASK_0 := MEM_SIZE - STACK_SIZE*MAX_TASKS    { Base address of task 0 }
        declare p[MEM_SIZE]  { parameter memory array }
        declare sp := TASK_0 + STACK_SIZE  { initial stack pointer }
        declare fp := TASK_0 + STACK_SIZE  { initial frame pointer }
        declare tx := 0   { active task index }
        declare p0 := 0   { initial global data allocation pointer }
        family tstate     { task states }
            declare id[MAX_TASKS] := (0)  { id = -1 active, id = 0 not used, id = CB task paused }
            declare sp[MAX_TASKS]
            declare fp[MAX_TASKS]
        end family
        tstate.id[0] := -1  { Only task 0 is initially active }
        declare exception_code := -1
    end function
'''

code = '''


on init
  tcm.init(100,1)
  declare q
  SET_CONDITION(TCM_DEBUG)
end on

taskfunc sum(x,y) -> result
  result := x + y
end taskfunc

on note
  q := call sum(1,2)
end on


'''

#import codecs
#code = codecs.open(r'D:\PythonProj\KScript EditorNewTest\test scripts\sample.txt', 'r', 'latin-1').read()

output = do_compile(code, optimize=True, extra_syntax_checks=True)
print()
print(output)
