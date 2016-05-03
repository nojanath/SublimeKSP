logger_code = """
// Activate the logger, if this is not called then the other functions will not be included in the code.
macro activate_logger(filepath)
	declare !#name#[32768]
	#name#[0] := "--- Logger Started ---"
	declare logger_count := 1
	declare @logger_filepath
	logger_filepath := filepath
	pgs_create_key(#name#_flag, 1)
	pgs_set_key_val(#name#_flag, 0, 1)
end macro

// Function goes at the start of the pgs callback
function checkPrintFlag()
	if pgs_get_key_val(#name#_flag, 0) = 1
		save_array_str(!#name#, logger_filepath)
		pgs_set_key_val(#name#_flag, 0, 0)
	end if
end function

// Print text to the logger, can be used anywhere
function print(text)
	!#name#[logger_count] := text
	inc(logger_count)
	pgs_set_key_val(#name#_flag, 0, 1)
end function
"""
# logger_code = """
# // Activate the logger, if this is not called then the other functions will not be included in the code.
# macro activate_logger(directory)
# 	declare !logger[32768]
# 	logger[0] := "--- Logger Started ---"
# 	declare logger_count := 1
# 	declare @logger_filepath
# 	logger_filepath := directory & "logger" & CURRENT_SCRIPT_SLOT & ".nka"
# 	pgs_create_key(logger_flag, 1)
# 	pgs_set_key_val(logger_flag, 0, 1)
# end macro

# // Function goes at the start of the pgs callback
# function checkPrintFlag()
# 	if pgs_get_key_val(logger_flag, 0) = 1
# 		save_array_str(!logger, logger_filepath)
# 		pgs_set_key_val(logger_flag, 0, 0)
# 	end if
# end function

# // Print text to the logger, can be used anywhere
# function print(text)
# 	!logger[logger_count] := text
# 	inc(logger_count)
# 	pgs_set_key_val(logger_flag, 0, 1)
# end function
# """
