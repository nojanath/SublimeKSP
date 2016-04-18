logger_code = """
// Activate the logger, if this is not called then the other functions will not be included in the code.
macro activate_logger(directory)
	declare !console[32768]
	console[0] := "--- Logger Started ---"
	declare console_count := 1
	declare @logger_filepath
	logger_filepath := directory & "console.nka"
	pgs_create_key(console_flag, 1)
	pgs_set_key_val(console_flag, 0, 1)
end macro

// Function goes at the start of the pgs callback
function checkPrintFlag()
	if pgs_get_key_val(console_flag, 0) = 1
		save_array_str(!console, logger_filepath)
		pgs_set_key_val(console_flag, 0, 0)
	end if
end function

// Print text to the logger, can be used anywhere
function print(text)
	!console[console_count] := text
	inc(console_count)
	pgs_set_key_val(console_flag, 0, 1)
end function
"""
