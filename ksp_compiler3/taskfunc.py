taskfunc_code = '''
/*
    Title: Task Control Module
    Author: R. D. Villwock
    First Written: February 7, 2012
    Current Version: 1.2
    Last Modified: December 28, 2022

    NOTICE: Robert Villwock and Nils Liberg have placed this source code into the
            public domain free from any copyright and full permission is hereby
            granted for anyone to incorporate this code in their Kontakt scripts.
            You must however assume any and all liability for its use and we provide
            no assurance or guarantee that it will perform in any specified way.

    --- Interface ---

    properties: tcm.exception()  read-only
                tcm.task()       read-only

    functions: tcm.init()
               tcm.pop()
               tcm.push()
               tcm.wait()
               tcm.wait_async()
               tcm.wait_ticks()

    exception constants: TOO_MANY_TASKS
                         STACK_OVERFLOW
                         STACK_UNDERFLOW
*/

// imports, initializes, and configures the TCM
macro tcm.init(stack_depth)
    // memory subsystem size
    USE_CODE_IF_NOT(TCM_LARGE)
        define MEM_SIZE := 32768
    END_USE_CODE
    USE_CODE_IF(TCM_LARGE)
        define MEM_SIZE := 1000000
    END_USE_CODE

    define STACK_SIZE := stack_depth                     // maximum stack depth allocated by user
    define MAX_TASKS := MEM_SIZE / STACK_SIZE - 1        // max tasks supported
    define TASK_0 := MEM_SIZE - STACK_SIZE * MAX_TASKS   // address of task 0

    // exception condition codes
    define TOO_MANY_TASKS := 1
    define STACK_OVERFLOW := 2
    define STACK_UNDERFLOW := 3

    declare p[MEM_SIZE]                 // allocate the task stacks
    declare sp := TASK_0 + STACK_SIZE   // stack pointer
    declare fp := TASK_0 + STACK_SIZE   // frame pointer
    declare tx                          // active task ID

    family tstate               // task states
        declare id[MAX_TASKS]   // callback ID, if not 0 (not used) or -1 (active task)
        declare sp[MAX_TASKS]   // task stack pointers
        declare fp[MAX_TASKS]   // task frame pointers
        declare fs[MAX_TASKS]   // task full-stack addresses
    end family

    // pre-compute the full-stack array
    for tx := 0 to MAX_TASKS - 1
        tstate.fs[tx] := TASK_0 + tx * STACK_SIZE
    end for

    tx := 0             // set initial task ID to zero
    tstate.id[0] := -1  // only task 0 is initially active

    // read only active task ID
    property tcm.task
        function get() -> result
            result := tx
        end function
    end property

    // read-only exception code
    USE_CODE_IF_NOT(TCM_DISABLE_EXCEPTION_HANDLING)
        property tcm.exception
            function get() -> result
                result := pgs_get_key_val(TCM_EXCEPTION, CURRENT_SCRIPT_SLOT)
            end function
        end property

        pgs_create_key(TCM_EXCEPTION, 5)    // one for each script slot

        // initially reset exception code for this script slot
        pgs_set_key_val(TCM_EXCEPTION, CURRENT_SCRIPT_SLOT, 0)
    END_USE_CODE
end macro


// pops value from the top of the active task stack
function tcm.pop() -> result
    // return the data value
    result := p[sp]

    USE_CODE_IF_NOT(TCM_DEBUG)
        // finish the pop
        inc(sp)
    END_USE_CODE

    USE_CODE_IF(TCM_DEBUG)
        // see if it's OK to finish pop
        call check_empty()
    END_USE_CODE
end function

// pushes value onto top of the active task stack
function tcm.push(value)
    dec(sp)
    p[sp] := value

    USE_CODE_IF(TCM_DEBUG)
        // check if this caused a stack overflow
        call check_full()
    END_USE_CODE
end function

// provides a thread-safe pause for current task
function tcm.wait(time)
    p[sp - 1] := time
    call _twait()
end function

// provides a thread-safe pause for current task, with wait time defined in MIDI ticks
function tcm.wait_ticks(ticks)
    p[sp - 1] := ticks
    call _twait_ticks()
end function

// provides a thread-safe pause for current asynchronous task
function tcm.wait_async(time)
    p[sp - 1] := time
    call _twait_async()
end function


/* INTERNAL FUNCTIONS */


function check_empty()
    if sp >= fp - 1
        // user stack area is empty, can't pop
        set_exception(STACK_UNDERFLOW)
    else
        // OK, finish the pop
        inc(sp)
    end if
end function

// checks for stack overflow
function check_full()
    // leave a guard for twait prolog
    if sp < (tstate.fs[tx] + 2)
        set_exception(STACK_OVERFLOW)
    end if
end function

// illustrative conditional prolog ending
function prolog_end()
    USE_CODE_IF(TCM_DEBUG)
        // call is only added to prolog in debug mode
        call check_full()
    END_USE_CODE
end function

// used by system code only
function set_exception(ecode)
    USE_CODE_IF_NOT(TCM_DISABLE_EXCEPTION_HANDLING)
        pgs_set_key_val(TCM_EXCEPTION, CURRENT_SCRIPT_SLOT, ecode)
    END_USE_CODE
end function

// inner function called by twait()
function _twait()
    // find next available task ID
    p[sp - 2] := search(tstate.id, 0)

    if p[sp - 2] = -1
        // no more left
        set_exception(TOO_MANY_TASKS)
    else
        // save current task's state
        tstate.id[tx] := NI_CALLBACK_ID
        tstate.fp[tx] := fp
        tstate.sp[tx] := sp

        // new task's ID
        tx := p[sp - 2]

        // now, initialize new active task state
        tstate.id[tx] := -1                     // this is now the active task
        fp := tstate.fs[tx] + STACK_SIZE        // empty stack for new task
        p[fp - 1] := p[sp - 1]                  // copy wait time to new task frame
        sp := fp                                // user stack intially empty

        // it's now OK to allow another callback or resume of a callback
        wait(p[sp - 1])

        // wait has timed out, awaken original task
        tstate.id[tx] := 0                      // active task can now be released to the pool
        tx := search(tstate.id, NI_CALLBACK_ID) // find pre-wait task ID
        tstate.id[tx] := -1                     // reactivate pre-wait task
        fp := tstate.fp[tx]                     // restore pre-wait pointers
        sp := tstate.sp[tx]
    end if
end function

// inner function called by twait_ticks()
function _twait_ticks()
    // find next available task ID
    p[sp - 2] := search(tstate.id, 0)

    if p[sp - 2] = -1
        // no more left
        set_exception(TOO_MANY_TASKS)
    else
        // save current task's state
        tstate.id[tx] := NI_CALLBACK_ID
        tstate.fp[tx] := fp
        tstate.sp[tx] := sp

        // new task's ID
        tx := p[sp - 2]

        // now, initialize new active task state
        tstate.id[tx] := -1                     // this is now the active task
        fp := tstate.fs[tx] + STACK_SIZE        // empty stack for new task
        p[fp - 1] := p[sp - 1]                  // copy wait time to new task frame
        sp := fp                                // user stack intially empty

        // It's now OK to allow another callback or resume of a callback
        wait_ticks(p[sp - 1])

        // wait has timed out, awaken original task
        tstate.id[tx] := 0                      // active task can now be released to the pool
        tx := search(tstate.id, NI_CALLBACK_ID) // find pre-wait task ID
        tstate.id[tx] := -1                     // reactivate pre-wait task
        fp := tstate.fp[tx]                     // restore pre-wait pointers
        sp := tstate.sp[tx]
    end if
end function

// inner function called by twait_async()
function _twait_async()
    // find next available task ID
    p[sp - 2] := search(tstate.id, 0)

    if p[sp - 2] = -1
        // no more left
        set_exception(TOO_MANY_TASKS)
    else
        // save current task's state
        tstate.id[tx] := NI_CALLBACK_ID
        tstate.fp[tx] := fp
        tstate.sp[tx] := sp

        // new task's ID
        tx := p[sp - 2]

        // now, initialize new active task state
        tstate.id[tx] := -1                     // this is now the active task
        fp := tstate.fs[tx] + STACK_SIZE        // empty stack for new task
        p[fp - 1] := p[sp - 1]                  // copy wait time to new task frame
        sp := fp                                // user stack intially empty

        // It's now OK to allow another callback or resume of a callback
        wait_async(p[sp - 1])

        // wait has timed out, awaken original task
        tstate.id[tx] := 0                      // active task can now be released to the pool
        tx := search(tstate.id, NI_CALLBACK_ID) // find pre-wait task ID
        tstate.id[tx] := -1                     // reactivate pre-wait task
        fp := tstate.fp[tx]                     // restore pre-wait pointers
        sp := tstate.sp[tx]
    end if
end function
'''