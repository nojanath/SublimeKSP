logger_code = """
// #name# is generated from the given filepath by the compiler.
// Activate the logger, if this is not called then the other functions will not be included in the code.
macro activate_logger(filepath)
	declare !#name#[32768]
	declare logger_count
	print("--- Logger Started ---")
	declare logger_previous_count
	declare @logger_filepath
	declare $LOGGER_ASYNC_ID
	logger_filepath := filepath
end macro

// This function is put at the end of the persistence_changed callback.
function checkPrintFlag()
	while 1=1
		// Only save array if there have been changes, for efficency.
		if logger_previous_count # logger_count 
			LOGGER_ASYNC_ID := save_array_str(!#name#, logger_filepath)
		end if
		logger_previous_count := logger_count
		wait(200000) // The time interval that the logger refreshes.
	end while
end function

// Print text to the logger, can be used anywhere.
function print(text)
	!#name#[logger_count] := text
	logger_count := (logger_count + 1) mod 32768
end function
"""
