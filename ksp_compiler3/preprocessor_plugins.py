# preprocessor_plugins.py
# Written by Sam Windell
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


#=================================================================================================
#=================================================================================================
# TO DO:
#	Check for bugs when using prefixes: $%@!
# 	Clean up functions.
# 	Test for bugs when using namespaces.
# 	Add a time and date comment to the output Kontakt script.
#	Re-evalulate the usefulness of the declare list command.
#	This should throw an exception, a non constant is used in the array initialisation:
#		declare array[6] := (get_ui_id(silder), 0) 
#	Some kind of multi-dimentional array would be nice.
#	Improve the error messages given by the compiler.
#	Improve the set_control_properties() command, (and the list used in the function)




import re
import collections

#=================================================================================================
#=================================================================================================
# Regular expressions
var_prefix_re = r"[%!@$]"

varname_re_string = r'((\b|[$%!@])[0-9]*[a-zA-Z_][a-zA-Z0-9_]*(\.[a-zA-Z_0-9]+)*)\b'
varname_re = re.compile(varname_re_string)
commas_not_in_parenth = re.compile(r",(?![^()]*\))") # All commas that are not in parenthesis
list_add_re = re.compile(r"^\s*list_add\s*\(")

# 'Regular expressions for 'blocks'
macro_start_re = re.compile(r'^\s*macro(?=\W)')
macro_end_re = re.compile(r'^\s*end\s+macro')
for_re = re.compile(r"^((\s*for)(\(|\s+))")
end_for_re = re.compile(r"^\s*end\s+for")
while_re = re.compile(r"^((\s*while)(\(|\s+))")
end_while_re = re.compile(r"^\s*end\s+while")
if_re = re.compile(r"^\s*if(\s+|\()")
end_if_re = re.compile(r"^\s*end\s+if")

ui_type_names = ['ui_button', "ui_switch", 'ui_knob', 'ui_label', 'ui_level_meter', 'ui_menu', 'ui_slider', 'ui_table', 'ui_text_edit', 'ui_waveform', "ui_value_edit"]
keywords_only = ["declare", "const", "pers", "polyphonic", "list"]
declare_keywords = keywords_only + ui_type_names


#=================================================================================================
#=================================================================================================
# These functions are called by the main compiler.

# For these, the macros have not yet been expaned.
def pre_macro_functions(lines):
	handle_define_lines(lines)
	handle_iterate_macro(lines)

# For these, the macros have been expaned.
def post_macro_functions(lines):
	handle_ui_arrays(lines)
	multi_dimensional_arrays(lines)
	inline_declare_assignment(lines)
	variable_persistence_shorthand(lines)
	ui_property_functions(lines)
	handle_lists(lines)
	calculate_open_size_array(lines)


#=================================================================================================
# For all of these functions, the 'lines' argument is a collections.deque of Line objects. All 
# code of this deque has already been imported with the 'import' command, and all comments have 
# been removed.



# Create multidimentional arrays. They are declared like this:
#	declare presetValues[10, 4, 5]
# You set and get values using the same pattern:
#	presetValues[5, 0, 0] := 100
#	message(presetValues[5, 0, 0])
# Each multidimentional has a set of built-in constants for the size of each dimension:
#	message(presetValues.SIZE_D1)
#	message(presetValues.SIZE_D2) // etc.. 
# This functions replaces the multidimensional array declaration with a property with appropriate
# get and set functions to be sorted by the compiler further down the line.
def multi_dimensional_arrays(lines):

	dimensions = []
	num_dimensions = []
	name = []
	line_numbers = []

	for i in range(len(lines)):
		line = lines[i].command.strip()
		if re.search(r"^\s*declare\s+.*" + varname_re_string + r"\s*\[\s*\w+\s*(\s*\,\s*\w+\s*)+\s*\]", line):

			variable_name = line[: line.find("[")]
			for keyword in declare_keywords:
				variable_name = variable_name.replace(keyword, "")
			variable_name = variable_name.strip()

			prefix = ""
			if re.search(var_prefix_re, variable_name):
				prefix = variable_name[0]
				variable_name = re.sub(var_prefix_re, "", variable_name)
			name.append(variable_name)

			dimensions_split = line[line.find("[") + 1 : line.find("]")].split(",") 
			num_dimensions.append(len(dimensions_split))
			dimensions.append(dimensions_split)

			line_numbers.append(i)

			new_text = line.replace(variable_name, prefix + "_" + variable_name)
			new_text = re.sub(r'\,', '*', new_text)
			lines[i].command = new_text

	if line_numbers:
		# add the text from the start of the file to the first declaration
		new_lines = collections.deque()
		for i in range(0, line_numbers[0] + 1):
			new_lines.append(lines[i])

		# for each declaration create the elements and fill in the gaps
		for i in range(len(line_numbers)):
	
			for ii in range(num_dimensions[i]):
				current_text = "declare const " + name[i] + ".SIZE_D" + str(ii + 1) + " := " + dimensions[i][ii]
				new_lines.append(lines[i].copy(current_text))

			# start property
			current_text = "property " + name[i]
			new_lines.append(lines[i].copy(current_text))

			# start get function
			# it might look something like this: function get(v1, v2, v3) -> result
			current_text = "function get(v1"
			for ii in range(1, num_dimensions[i]):
				current_text = current_text + ", v" + str(ii + 1) 
			current_text = current_text + ") -> result"
			new_lines.append(lines[i].copy(current_text))

			# get function body
			current_text = "result := _" + name[i] + "["
			for ii in range(num_dimensions[i]):
				if ii != num_dimensions[i] - 1: 
					for iii in range(num_dimensions[i] - 1, ii, -1):
						current_text = current_text + dimensions[i][iii] + " * "
				current_text = current_text + "v" + str(ii + 1)
				if ii != num_dimensions[i] - 1:
					current_text = current_text + " + "
			current_text = current_text + "]"
			new_lines.append(lines[i].copy(current_text))

			# end get function
			new_lines.append(lines[i].copy("end function"))

			# start set function
			# it might look something like this: function set(v1, v2, v3, val)
			current_text = "function set(v1"
			for ii in range(1, num_dimensions[i]):
				current_text = current_text + ", v" + str(ii + 1) 
			current_text = current_text + ", val)"
			new_lines.append(lines[i].copy(current_text))

			# set function body
			current_text = "_" + name[i] + "["
			for ii in range(num_dimensions[i]):
				if ii != num_dimensions[i] - 1: 
					for iii in range(num_dimensions[i] - 1, ii, -1):
						current_text = current_text + dimensions[i][iii] + " * "
				current_text = current_text + "v" + str(ii + 1)
				if ii != num_dimensions[i] - 1:
					current_text = current_text + " + "
			current_text = current_text + "] := val"
			new_lines.append(lines[i].copy(current_text))

			# end set function
			new_lines.append(lines[i].copy("end function"))		

			# end property
			new_lines.append(lines[i].copy("end property"))


			if i + 1 < len(line_numbers):
				for ii in range(line_numbers[i] + 1, line_numbers[i + 1] + 1):
					new_lines.append(lines[ii])

		# add the text from the last declaration to the end of the document
		for i in range(line_numbers[len(line_numbers) - 1] + 1, len(lines)):
			new_lines.append(lines[i])

		# both lines and new lines are deques of Line objects, replace lines with new lines
		for i in range(len(lines)):
			lines.pop()
		lines.extend(new_lines)	

		for line_obj in lines:
			print(line_obj.command)



def ui_property_functions(lines):

	property_text = [
	"set_slider_properties",
	"set_switch_properties",
	"set_label_properties",
	"set_menu_properties",
	"set_table_properties",
	"set_button_properties",
	"set_level_meter_properties",
	"set_waveform_properties",
	"set_knob_properties",
	"set_bounds" ]

	property_params = [
	"default", "picture", "mouse_behaviour",
	"text", "picture", "text_alignment", "font_type", "textpos_y",
	"text", "picture", "text_alignment", "font_type", "textpos_y",
	"picture", "font_type", "text_alignment", "textpos_y",
	"bar_color", "zero_line_color",
	"text", "picture", "text_alignment", "font_type", "textpos_y",
	"bg_color", "off_color", "on_color", "overload_color",
	"bar_color", "zero_line_color",
	"text", "default",
	"x", "y", "width", "height" ]

	max_num_props = [
	3,	5,	5,	4,	2,	5,	4,	2,	2,	4 ]

	line_numbers = []
	prop_numbers = []
	var_names = []
	num_params = []
	params = []

	for i in range(len(lines)):
		line = lines[i].command.strip()
		for ii in range(len(property_text)):
			if line.startswith(property_text[ii]):
				commma_sep = line[line.find(",") + 1 : len(line) - 1]
				line_numbers.append(i)
				prop_numbers.append(ii)

				variable_name = line[line.find("(") + 1 : line.find(",")]
				var_names.append(variable_name)

				string_list = re.split(commas_not_in_parenth, commma_sep)
				params.append(string_list)
				num_params.append(len(string_list))
				lines[i].command = ""

	if line_numbers:
		# add the text from the start of the file to the first declaration
		new_lines = collections.deque()
		for i in range(0, line_numbers[0] + 1):
			new_lines.append(lines[i])

		# for each declaration create the elements and fill in the gaps
		for i in range(len(line_numbers)):
	
			sum_max = 0			
			for ii in range(0, prop_numbers[i]):
				sum_max += max_num_props[ii]

			for ii in range(num_params[i]):
				current_text = var_names[i] + " -> " + property_params[sum_max + ii] + " := " + params[i][ii]
				new_lines.append(lines[i].copy(current_text))	

			if i + 1 < len(line_numbers):
				for ii in range(line_numbers[i] + 1, line_numbers[i + 1] + 1):
					new_lines.append(lines[ii])

		# add the text from the last declaration to the end of the document
		for i in range(line_numbers[len(line_numbers) - 1] + 1, len(lines)):
			new_lines.append(lines[i])

		# both lines and new lines are deques of Line objects, replace lines with new lines
		for i in range(len(lines)):
			lines.pop()
		lines.extend(new_lines)	



def inline_declare_assignment(lines):

	line_numbers = []
	var_text = []

	for i in range(len(lines)):
		line = lines[i].command.strip()
		ls_line = re.sub(r"\s", "", line)
		if ls_line.startswith("declare") == True and re.search(r':=', line) != None and re.search(r'const\s', line) == None:
			pre_assignment_text = line[: line.find(":=")]
			if not "[" in pre_assignment_text:
				variable_name = pre_assignment_text
				for keyword in declare_keywords:
					variable_name = variable_name.replace(keyword, "")
				variable_name = variable_name.strip()

				line_numbers.append(i)

				var_text.append(variable_name + " " + line[line.find(":=") :])
				lines[i].command = pre_assignment_text

	if line_numbers:
		# add the text from the start of the file to the first declaration
		new_lines = collections.deque()
		for i in range(0, line_numbers[0] + 1):
			new_lines.append(lines[i])

		# for each declaration create the elements and fill in the gaps
		for i in range(len(line_numbers)):

			# new_lines.append(Line(var_text[i], [(filename, int(line_numbers[i]) + 2)]))	
			new_lines.append(lines[i].copy(var_text[i]))	
			# lines[i].copy(var_text[i])

			if i + 1 < len(line_numbers):
				for ii in range(line_numbers[i] + 1, line_numbers[i + 1] + 1):
					new_lines.append(lines[ii])

		# add the text from the last declaration to the end of the document
		for i in range(line_numbers[len(line_numbers) - 1] + 1, len(lines)):
			new_lines.append(lines[i])

		# both lines and new lines are deques of Line objects, replace lines with new lines
		for i in range(len(lines)):
			lines.pop()
		lines.extend(new_lines)	



def handle_lists(lines):

	list_names = []
	line_numbers = []
	init_flag = None
	loop_flag = None
	iterators = []

	for i in range(len(lines)):
		line = lines[i].command
		if re.search(r"^\s*on\s+init", line):
			init_flag = True
		elif re.search(r"^\s*end\s+on", line):
			if init_flag == True:
				for ii in range(len(iterators)):
					list_declare_line = lines[line_numbers[ii]].command
					square_bracket_pos = list_declare_line.find("[]") + 1
					lines[line_numbers[ii]].command = list_declare_line[: square_bracket_pos] + str(iterators[ii]) + "]"
				init_flag = False
		elif re.search(for_re, line) or re.search(while_re, line) or re.search(if_re, line):
			loop_flag = True
		elif re.search(end_for_re, line) or re.search(end_while_re, line) or re.search(end_if_re, line):
			loop_flag = False
		elif re.search(r'\s+list\s+', line) and re.search(r'^\s*declare\s+', line):
			s = re.search(r'\s+list\s+' + varname_re_string, line)
			if s:
				name = s.group(0).replace("list", "").strip()
				list_names.append(name)
				line_numbers.append(i)
				iterators.append(0)
				# the number of elements is populated at the end of the init callback
				lines[i].command = "declare " + name + "[]"
		else:
			# ls_line = re.sub(r"\s", "", line)
			if re.search(list_add_re, line):
				find_list_name = False
				for ii in range(len(list_names)):
					if re.sub(var_prefix_re, "", list_names[ii]) in line:
						find_list_name = True
						if loop_flag == True:
							raise ParseException(lines[i], "list_add() cannot be used in loops or if statements.\n")
						if init_flag == False:
							raise ParseException(lines[i], "list_add() can only be used in the init callback.\n")

						value = line[line.find(",") + 1 : len(line) - 1]
						lines[i].command = list_names[ii] + "[" + str(iterators[ii]) + "] := " + value
						iterators[ii] += 1
				if not find_list_name:
					undeclared_name = line[line.find("(") + 1 : line.find(",")]
					raise ParseException(lines[i], undeclared_name + " had not been declared.\n") 



def calculate_open_size_array(lines):

	string_var_names = []
	strings = []
	line_numbers = []
	num_ele = []

	for i in range(len(lines)):
		line = lines[i].command
		ls_line = line.replace(" ", "").replace("	", "")
		if "[]:=(" in ls_line:
			commma_sep = line[line.find("(") + 1 : len(line) - 1]
			string_list = re.split(commas_not_in_parenth, commma_sep)
			num_elements = len(string_list)

			lines[i].command = line[: line.find("[") + 1] + str(num_elements) + line[line.find("[") + 1 :]
		# convert text array declaration to multiline
		if re.search(r'\s+!\w+', line) != None and "declare" in line and ":=" in line:
			commma_sep = line[line.find("(") + 1 : len(line) - 1]
			string_list = re.split(commas_not_in_parenth, commma_sep)
			num_elements = len(string_list)
			
			search_obj = re.search(r'\s+!\w+', line)
			string_var_names.append(search_obj.group(0))

			num_ele.append(num_elements)
			strings.append(string_list)
			line_numbers.append(i)

			
	# for some reason this doesnt work in the loop above...?
	for lineno in line_numbers: 
		lines[lineno].command = lines[lineno].command[: lines[lineno].command.find(":")]


	if line_numbers:
		# add the text from the start of the file to the first declaration
		new_lines = collections.deque()
		for i in range(0, line_numbers[0] + 1):
			new_lines.append(lines[i])

		# for each declaration create the elements and fill in the gaps
		for i in range(len(line_numbers)):

			for ii in range(num_ele[i]):
				current_text = string_var_names[i] + "[" + str(ii) + "] := " + strings[i][ii] 
				new_lines.append(lines[i].copy(current_text))

			if i + 1 < len(line_numbers):
				for ii in range(line_numbers[i] + 1, line_numbers[i + 1] + 1):
					new_lines.append(lines[ii])

		# add the text from the last declaration to the end of the document
		for i in range(line_numbers[len(line_numbers) - 1] + 1, len(lines)):
			new_lines.append(lines[i])

		# both lines and new lines are deques of Line objects, replace lines with new lines
		for i in range(len(lines)):
			lines.pop()
		lines.extend(new_lines)	



def variable_persistence_shorthand(lines):
	''' handle the variable persistence shorthand'''
	line_numbers = []
	variable_names = []


	for i in range(len(lines)):
		line = lines[i].command.strip()
		if re.search(r"^\s*declare\s+pers\s+", line):

			variable_name = line
			for word in declare_keywords:
				variable_name = variable_name.replace(word, "")

			if variable_name.find("[") != -1:
				variable_name = variable_name.replace(variable_name[variable_name.find("[") : ], "")
			if variable_name.find("(") != -1:
				variable_name = variable_name.replace(variable_name[variable_name.find("(") : ], "")

			variable_names.append(variable_name.strip())
			line_numbers.append(i)
			lines[i].command = lines[i].command.replace("pers", "")

	if line_numbers:
		# add the text from the start of the file to the first declaration
		new_lines = collections.deque()
		for i in range(0, line_numbers[0] + 1):
			new_lines.append(lines[i])

		# for each declaration create the elements and fill in the gaps
		for i in range(len(variable_names)):

			current_text = "make_persistent(" + variable_names[i] + ")"
			new_lines.append(lines[i].copy(current_text))

			if i + 1 < len(line_numbers):
				for ii in range(line_numbers[i] + 1, line_numbers[i + 1] + 1):
					new_lines.append(lines[ii])

		# add the text from the last declaration to the end of the document
		for i in range(line_numbers[len(line_numbers) - 1] + 1, len(lines)):
			new_lines.append(lines[i])

		# both lines and new lines are deques of Line objects, replace lines with new lines
		for i in range(len(lines)):
			lines.pop()
		lines.extend(new_lines)	



def handle_iterate_macro(lines):
	''' handle the iterate_macro command '''

	min_val = []
	max_val = []
	step_val = []
	macro_name = []
	line_position = []
	downto = []

	for index in range(len(lines)):
		line = lines[index].command
		if re.search(r"^\s*iterate_macro\(", line):
			name = line[line.find("(") + 1 : line.find(")")]
			params = line[line.find(")") + 1:]
			try:
				if "downto" in params:
					to_stmt = "downto"
					downto.append(True)
				elif "to" in params:
					to_stmt = "to"
					downto.append(False)

				minv = eval(params[params.find(":=") + 2 : params.find(to_stmt)])
				if "step" in params:
					step = eval(params[params.find("step") + 4 :])
					maxv = eval(params[params.find(to_stmt) + len(to_stmt) : params.find("step")])
				else:
					step = 1
					maxv = eval(params[params.find(to_stmt) + len(to_stmt) :])

				if (minv > maxv and to_stmt == "to") or (minv < maxv and to_stmt == "downto"):
					raise ParseException(lines[index], "Min and max values are incorrectly weighted (For example, min > max when it should be min < max)./n")

			except:
				raise ParseException(lines[index], "Incorrect values in iterate_macro statement. Native 'declare const' variables cannot be used here, instead a 'define' const must be used. " + \
						"The macro you are iterating must have only have 1 integer parameter, this will be replaced by the values in the chosen range.\n")

			macro_name.append(name)
			min_val.append(minv)
			max_val.append(maxv)
			step_val.append(step)
			line_position.append(index)

			lines[index].command = re.sub(r'[^\r\n]', '', line)

	if macro_name:
		# add the text from the start of the file to the first array declaration
		new_lines = collections.deque()
		for i in range(0, line_position[0] + 1):
			new_lines.append(lines[i])

		# for each array declaration create the elements and fill in the gaps
		for i in range(len(macro_name)):

			step = int(step_val[i])
			offset = 1
			if downto[i]:
				step = -step
				offset = -1

			for ii in range(int(min_val[i]), int(max_val[i]) + offset, step):
				current_text = macro_name[i] + "(" + str(ii) + ")"
				new_lines.append(lines[i].copy(current_text))

			if i + 1 < len(line_position):
				for ii in range(line_position[i] + 1, line_position[i + 1] + 1):
					new_lines.append(lines[ii])

		# add the text from the last array declaration to the end of the document
		for i in range(line_position[len(line_position) - 1] + 1, len(lines)):
			new_lines.append(lines[i])

		# both lines and new lines are deques of Line objects, replace lines with new lines
		for i in range(len(lines)):
			lines.pop()
		lines.extend(new_lines)	




def handle_define_lines(lines):
	''' handle define lines '''
	define_titles = []
	define_values = []
	define_line_pos = []
	for index in range(len(lines)):
		line = lines[index].command 
		ls_line = line.lstrip() # remove whitespace from beginning
		if re.search(r"^\s*define", line):
			if re.search(r"^\s*define\s+" + varname_re_string + r"\s*:=", line):
				text_without_define_helper = ls_line.replace('define ', '').replace("#", "")
				text_without_define = text_without_define_helper.lstrip()
				colon_bracket_pos = text_without_define.find(":=")

				# find the title
				title = text_without_define[0 : (colon_bracket_pos - len(text_without_define))].replace(" ", "")
				define_titles.append(title)

				# find the value
				value = text_without_define[colon_bracket_pos + 2 : len(text_without_define)].replace(" ", "")
				define_values.append(value)

				define_line_pos.append(index)
				# remove the line
				lines[index].command = re.sub(r'[^\r\n]', '', line)
			else:
				raise ParseException(lines[index], "Syntax error.\n")

	# if at least one define const exsists
	if define_titles:
		# check each of the values to see if they contain any other define consts
		for i in range(len(define_values)):
			for ii in range(len(define_titles)):
				if define_titles[ii] in define_values[i]:
					define_values[i] = define_values[i].replace(define_titles[ii], define_values[ii])

		# do any maths if needed
		for i in range(len(define_values)):
			try:
				eval(define_values[i])
			except:
				raise ParseException(lines[define_line_pos[i]], "Undeclared variable in define statement.\n")

		# scan the code can replace any occurances of the variable with it's value
		for line_obj in lines:
			line = line_obj.command 
			for index, item in enumerate(define_titles):
				if re.search(r"\b" + item + r"\b", line):
					# character_before = line[line.find(item) - 1 : line.find(item)]  
					# if character_before.isalpha() == False and character_before.isdiget() == False:  
					line_obj.command = line_obj.command.replace(item, define_values[index])


def handle_ui_arrays(lines):
	''' handle ui arrays '''


	ui_declaration = []
	variable_names = []
	array_declare_pos = []
	num_elements = []
	table_elements = []
	pers_state = []

	# find all of the array declarations
	for index in range(len(lines)):
		line = lines[index].command 
		ls_line = line.lstrip() # remove whitespace from beginning
		if re.search(r"^\s*declare\s+", line) and line.find("[") != -1 :
			for ui_type in ui_type_names:
				if ui_type in line:

					bracket_pos = ls_line.find("]")
					proceed = False
					if bracket_pos != -1:
						if ui_type != "ui_table":
							proceed = True
						elif ls_line.find("[", bracket_pos + 1) != -1:
							proceed = True

					if proceed == True:
						try:
							num_element = eval(ls_line[ls_line.find("[") + 1 : ls_line.find("]")])
						except:
							raise ParseException(lines[index], "Incorrect number of elements. Native 'declare const' variables cannot be used here, instead a 'define' const must be used.\n")

						# find the variable name
						variable_name = line[: line.find("[")].replace(ui_type, "")
						for word in keywords_only:
							variable_name = variable_name.replace(word, "")
						variable_name_no_pre = re.sub(var_prefix_re, "", variable_name)

						if re.search(r"\s+pers\s+", line):
							pers_state.append(True)
						else:  
							pers_state.append(False)

						# if there are parameters
						if "(" in ls_line:
							if ui_type == "ui_table":
								first_close_bracket = ls_line.find("]") + 1
								table_elements = ls_line[ls_line.find("[", first_close_bracket) + 1 : ls_line.find("]", first_close_bracket)]
								ui_declaration.append("declare " + ui_type + " " + variable_name + "[" + table_elements + "]" + ls_line[ls_line.find("(") : ls_line.find(")") + 1]) 
							else:
								ui_declaration.append("declare " + ui_type + " " + variable_name + ls_line[ls_line.find("(") : ls_line.find(")") + 1]) 
						else:
							ui_declaration.append("declare " + ui_type + " " + variable_name) 
						array_declare_pos.append(index)
						num_elements.append(num_element)
						variable_names.append(variable_name_no_pre)
						lines[index].command  = "declare " + variable_name_no_pre + "[" + str(num_element) + "]"

	# if at least one ui array exsists
	if ui_declaration:
		# add the text from the start of the file to the first array declaration
		new_lines = collections.deque()
		for i in range(0, array_declare_pos[0] + 1):
			new_lines.append(lines[i])

		# for each array declaration create the elements and fill in the gaps
		for i in range(len(ui_declaration)):

			num_eles = int(num_elements[i])

			for ii in range(0, num_eles):

				if "(" in ui_declaration[i]:
					if "[" in ui_declaration[i]:
						parameter_start = ui_declaration[i].find("[")
					else:
						parameter_start = ui_declaration[i].find("(")
					current_text = ui_declaration[i][:parameter_start] + str(ii) + ui_declaration[i][parameter_start:]
				else:
					current_text = ui_declaration[i] + str(ii)

				if pers_state[i] == True:
					current_text = current_text.strip()
					current_text = current_text[: 7] + " pers " + current_text[8 :]


				# add individual ui declaration
				new_lines.append(lines[i].copy(current_text))

				# add ui to array
				add_to_array_text = variable_names[i] + "[" + str(ii) + "]" + " := get_ui_id(" + variable_names[i] + str(ii) + ")"
				new_lines.append(lines[i].copy(add_to_array_text))

			if i + 1 < len(array_declare_pos):
				for ii in range(array_declare_pos[i] + 1, array_declare_pos[i + 1] + 1):
					new_lines.append(lines[ii])

		# add the text from the last array declaration to the end of the document
		for i in range(array_declare_pos[len(array_declare_pos) - 1] + 1, len(lines)):
			new_lines.append(lines[i])

		# both lines and new lines are deques of Line objects, replace lines with new lines
		for i in range(len(lines)):
			lines.pop()
		lines.extend(new_lines)
