logger_code = """
// Activate the logger, if this is not called then the other functions will not be included in the code.
macro activate_logger(filepath)
	declare !#name#[32768]
	declare logger_count
	print("--- Logger Started ---")
	declare logger_previous_count
	declare @logger_filepath
	logger_filepath := filepath
end macro

// Function goes at the end of the persistence_changed callback
function checkPrintFlag()
	while 1=1
		// Only save array if there have been changes, for efficency.
		if logger_previous_count # logger_count 
			save_array_str(!#name#, logger_filepath)
		end if
		logger_previous_count := logger_count
		wait(200000)
	end while
end function

// Print text to the logger, can be used anywhere
function print(text)
	!#name#[logger_count] := text
	inc(logger_count)
end function
"""
