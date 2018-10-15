
# Preprocessor Plugins
#
# This file is part of the SublimeKSP Compiler which is released under GNU General Public License version 3.
# For more information visit https://github.com/nojanath/SublimeKSP.
#
# This file adds a selection of extra syntax, functions and macros that aim to make programming in the
# Kontakt scripting language nicer. These functions are executed very near the beginning of the
# compiling process. They work by scanning through the deque of Line objects, and using regex, the
# line commands are manipulated or added to.

#=================================================================================================
# IDEAS:
# 	+= -= operators
#	UI functions to receive arguments in any order: set_bounds(slider, width := 50, x := 20)
#	get_ui_id() shorthand such as variable -> id
#	Multidimensional PGS keys
#	Single line if statements
#	A psuedo callback for UI arrays that automatically creates all the callbacks

import copy
import re
import math
import collections
import ksp_compiler
from simple_eval import SimpleEval
import time
from time import strftime, localtime

#=================================================================================================
varPrefixRe = r"[?~%!@$]"
variableNameRe = r'(?P<whole>(?P<prefix>\b|[?~$%!@])(?P<name>[a-zA-Z0-9_][a-zA-Z0-9_\.]*))\b' # A variable name
variableNameUnRe = r'((\b|[?~$%!@])[0-9]*[a-zA-Z0-9_][a-zA-Z0-9_]*(\.[a-zA-Z_0-9]+)*)\b' # Same as above but without names
persistenceRe = r"(?:\b(?P<persistence>pers|instpers|read)\s+)?"
nameInDeclareStmtRe = r"%s\s*(?=[\[\(\:]|$)" % variableNameRe # Match the variable name in a whole declare statement.

stringOrPlaceholderRe = r'({\d+}|\"[^"]*\")'
variableOrInt = r"[^\]]+" # Something that is not a square bracket closing
commasNotInBrackets = re.compile(r",(?![^\(\)\[\]]*[\)\]])") # All commas that are not in parenthesis.

forRe = re.compile(r"^for(?:\(|\s+)")
endForRe = re.compile(r"^end\s+for$")
whileRe = re.compile(r"^while(?:\(|\s+)")
endWhileRe = re.compile(r"^end\s+while$")
ifRe = re.compile(r"^if(?:\s+|\()")
endIfRe = re.compile(r"^end\s+if$")
familyStartRe = r"^family\s+(?P<famname>.+)$"
familyEndRe = r"^end\s+family$"
initRe = r"^on\s+init$"
endOnRe = r"^end\s+on$"

concatSyntax = "concat" # The name of the function to concat arrays.
stringEvaluator = SimpleEval() # Object used to evaluate strings as maths expressions.

#=================================================================================================
def pre_macro_functions(lines):
	""" This function is called before the macros have been expanded. lines is a collections.deque
	of Line objects - see ksp_compiler.py."""
	createBuiltinDefines(lines)
	removeActivateLoggerPrint(lines)
	handleDefineConstants(lines)
	# Define literals are only avilable for backwards compatibility as regular defines now serve this purpose.
	handleDefineLiterals(lines)

def macro_iter_functions(lines):
	""" Will process macro iteration and return true if any were found """
	return (handleIterateMacro(lines) or handleLiterateMacro(lines))

def post_macro_functions(lines):
	""" This function is called after the regular macros have been expanded. lines is a
	collections.deque of Line objects - see ksp_compiler.py."""
	handleIncrementer(lines)
	handleConstBlock(lines)
	handleStructs(lines)
	handleUIArrays(lines)
	handleSameLineDeclaration(lines)
	handleMultidimensionalArrays(lines)
	handleListBlocks(lines)
	handleOpenSizeArrays(lines)
	handlePersistence(lines)
	handleLists(lines)
	handleUIFunctions(lines)
	handleStringArrayInitialisation(lines)
	handleArrayConcat(lines)

#=================================================================================================
def simplfyAdditionString(string):
	""" Evaluates a string of add operations, any add pairs that cannot be evalutated are left.
	e.g. "2 + 2 + 3 + 4 + x + y + 2" => "11 + x + y + 2 """
	parts = string.split("+")
	count = 0
	while count < len(parts) - 1:
		try:
			simplified = int(parts[count]) + int(parts[count+1])
			parts[count] = str(simplified)
			parts.remove(parts[count + 1])
		except:
			count += 1
			pass
	return("+".join(parts))

def tryStringEval(expression, line, name):
	""" Evaluates a maths expression in the same way Kontakt would (only integers). """
	try:
		final = stringEvaluator.eval(str(expression).strip())
	except:
		raise ksp_compiler.ParseException(line,
			"Invalid syntax in %s value. This number must able to be evaluated to a single number at compile time; use only define constants, numbers or maths operations here.\n" % name)
	return (final)

def replaceLines(original, new):
	original.clear()
	original.extend(new)

def countFamily(lineText, famCount):
	""" Checks the line for family start or end and returns the current family depth """
	if lineText.startswith("family ") or lineText.startswith("family	"):
		famCount += 1
	elif famCount != 0:
		if re.search(familyEndRe, lineText):
			famCount -= 1
	return(famCount)

def inspectFamilyState(lines, textLineno):
	""" If the given line is in at least 1 family, return the family prefixes. """
	currentFamilyNames = []
	for i in range(len(lines)):
		if i == textLineno:
			if currentFamilyNames:
				return (".".join(currentFamilyNames) + ".")
			else:
				return (None)
			break
		line = lines[i].command.strip()
		if "family" in line:
			m = re.search(familyStartRe, line)
			if m:
				currentFamilyNames.append(m.group("famname"))
			elif re.search(familyEndRe, line):
				currentFamilyNames.pop()

#=================================================================================================
#=================================================================================================
class StructMember(object):
	def __init__(self, name, command, prefix):
		self.name = name
		self.command = command
		self.prefix = prefix # The prefix symbol of the member (@!%$)
		self.numElements = None

	def makeMemberAnArray(self, numElements):
		""" Make the command of this member into an array. numElements is a string of any amount of numbers seperated by commas.
		Structs exploit the fact the you can put the square brackets of an array after any 'subname' of a dot seperated name. """
		cmd = self.command
		if "[" in self.command:
			bracketLocation = cmd.find("[")
			self.command = cmd[: bracketLocation + 1] + numElements + ", " + cmd[bracketLocation + 1 :]
		else:
			self.command = re.sub(r"\b%s\b" % self.name, "%s[%s]" % (self.name, numElements), cmd)
			if ":=" in self.command:
				assignOperatorLocation = self.command.find(":=") + 2
				self.command = "%s(%s)" % (self.command[ : assignOperatorLocation], self.command[assignOperatorLocation : ])
		if self.prefix == "@":
			self.prefix = "!"

	def addNamePrefix(self, namePrefix):
		""" Add the prefix to the member with a dot operator. """
		self.command = re.sub(r"\b%s\b" % self.name, "%s%s.%s" % (self.prefix, namePrefix, self.name), self.command)

class Struct(object):
	def __init__(self, name):
		self.name = name
		self.members = []

	def addMember(self, memberObj):
		self.members.append(memberObj)
	def deleteMember(self, index):
		del self.members[index]
	def insertMember(self, location, memberObj):
		self.members.insert(location, memberObj)

def handleStructs(lines):
	structSyntax = "\&"
	structs = []

	def findStructs():
		""" Find all the struct blocks and build struct objects of them. """
		isCurrentlyInAStructBlock = False
		for lineIdx in range(len(lines)):
			line = lines[lineIdx].command.strip()

			# Find the start of a struct block
			if line.startswith("struct"):
				m = re.search(r"^struct\s+%s$" % variableNameRe, line)
				if m:
					structObj = Struct(m.group("name"))
					if isCurrentlyInAStructBlock:
						raise ksp_compiler.ParseException(lines[lineIdx], "Struct definitions cannot be nested.\n")
					isCurrentlyInAStructBlock = True
					lines[lineIdx].command = ""

			# Find the end of a struct block
			elif line.startswith("end"):
				if re.search(r"^end\s+struct$", line):
					isCurrentlyInAStructBlock = False
					structs.append(structObj)
					lines[lineIdx].command = ""

			# If in a struct, add each member as an object to the struct
			elif isCurrentlyInAStructBlock:
				if line:
					if not line.startswith("declare ") and not line.startswith("declare	"):
						raise ksp_compiler.ParseException(lines[lineIdx], "Structs may only consist of variable declarations.\n")
					m = re.search(nameInDeclareStmtRe, line)
					if m:
						variableName = m.group("whole")
						structDeclMatch = re.search(r"\&\s*%s" % variableNameRe, line)
						if structDeclMatch:
							variableName = "%s%s %s" % ("&", structDeclMatch.group("whole"), variableName)
					prefixSymbol = ""
					if re.match(varPrefixRe, variableName):
						prefixSymbol = variableName[:1]
						variableName = variableName[1:]
					structObj.addMember(StructMember(variableName, line.replace("%s%s" % (prefixSymbol, variableName), variableName), prefixSymbol))
				lines[lineIdx].command = ""
	findStructs()

	if structs:
		# Make the struct names a list so they are easily searchable
		structNames = [structs[i].name for i in range(len(structs))]

		def resolveStructsWithinStructs():
			""" Where structs have been declared as members of another struct, flatten them. """
			for i in range(len(structs)):
				j = 0
				counter = 0
				stillRemainginStructs = False
				# Struct member may themselves have struct members, so this is looped until it is fully resolved.
				while j < len(structs[i].members) or stillRemainginStructs == True:
					m = re.search(r"^([^%s]+\.)?%s\s*%s\s+%s" % (structSyntax, structSyntax, variableNameUnRe, variableNameUnRe), structs[i].members[j].name)
					if m:
						structs[i].deleteMember(j)
						structNum = structNames.index(m.group(2))
						structVariable = m.group(5).strip()
						if m.group(1):
							structVariable = m.group(1) + structVariable
						if structNum == i:
							raise ksp_compiler.ParseException(lines[0], "Declared struct cannot be the same as struct parent.\n")

						insertLocation = j
						for memberIdx in range(len(structs[structNum].members)):
							structMember = structs[structNum].members[memberIdx]
							varName = structVariable + "." + structMember.name
							newCommand = re.sub(r"\b%s\b" % structMember.name, varName, structMember.command)
							structs[i].insertMember(insertLocation, StructMember(varName, newCommand, structMember.prefix))
							insertLocation += 1

						# If there are still any struct member declarations, keep looping to resolve them.
						for name in structs[i].members[j].name:
							mm = re.search(r"^(?:[^%s]+\.)?%s\s*%s\s+%s" % (structSyntax, structSyntax, variableNameUnRe, variableNameUnRe), name)
							if mm:
								stillRemainginStructs = True
					j += 1

					if j >= len(structs[i].members) and stillRemainginStructs:
						stillRemainginStructs = False
						j = 0
						counter += 1
						if counter > 100000:
							raise ksp_compiler.ParseException(lines[0], "ERROR! Too many iterations while building structs.")
							break
		resolveStructsWithinStructs()

		def findAndHandleStructInstanceDeclarations():
			""" Find all places where an instance of a struct has been declared and build the lines necesary. """
			newLines = collections.deque()
			for i in range(len(lines)):
				line = lines[i].command.strip()
				m = re.search(r"^declare\s+%s\s*%s\s+%s(?:\[(.*)\])?$" % (structSyntax, variableNameUnRe, variableNameUnRe), line)
				if m:
					structName = m.group(1)
					declaredName = m.group(4)
					try:
						structIdx = structNames.index(structName)
					except ValueError:
						raise ksp_compiler.ParseException(lines[i], "Undeclared struct %s\n" % structName)

					newMembers = copy.deepcopy(structs[structIdx].members)
					# If necessary make the struct members into arrays.
					arrayNumElements = m.group(7)
					if arrayNumElements:
						for j in range(len(newMembers)):
							newMembers[j].makeMemberAnArray(arrayNumElements)
						if "," in arrayNumElements:
							arrayNumElements = ksp_compiler.split_args(arrayNumElements, lines[i])
							for dimIdx in range(len(arrayNumElements)):
								newLines.append(lines[i].copy("declare const %s.SIZE_D%d := %s" % (declaredName, dimIdx + 1, arrayNumElements[dimIdx])))
						else:
							newLines.append(lines[i].copy("declare const %s.SIZE := %s" % (declaredName, arrayNumElements)))

					# Add the declared names as a prefix and add the memebers to the newLines deque
					for j in range(len(newMembers)):
						newMembers[j].addNamePrefix(declaredName)
						newLines.append(lines[i].copy(newMembers[j].command))
				else:
					newLines.append(lines[i])

			replaceLines(lines, newLines)
		findAndHandleStructInstanceDeclarations()

#=================================================================================================
# Remove print functions when the activate_logger() is not present.
def removeActivateLoggerPrint(lines):
	printLineNumbers = []
	loggerActiveFlag = False
	for i in range(len(lines)):
		line = lines[i].command.strip()
		if re.search(r"^activate_logger\s*\(", line):
			loggerActiveFlag = True
		if re.search(r"^print\s*\(", line):
			printLineNumbers.append(i)

	if not loggerActiveFlag:
		for i in range(len(printLineNumbers)):
			lines[printLineNumbers[i]].command = ""

#=================================================================================================
class Incrementer(object):
	def __init__(self, name, start, step):
		self.name = name
		self.iterationVal = start
		self.step = step
	def increaseVal(self):
		self.iterationVal += self.step

def handleIncrementer(lines):
	iterObjs = []
	for i in range(len(lines)):
		line = lines[i].command.strip()
		# Check for START_INC and add the object to the array.
		if line.startswith("START_INC"):
			mm = re.search(r"^%s\s*\(\s*%s\s*\,\s*(.+)s*\,\s*(.+)\s*\)" % ("START_INC", variableNameUnRe), line)
			if mm:
				lines[i].command = ""
				iterObjs.append(Incrementer(mm.group(1), tryStringEval(mm.group(4), lines[i], "start"), tryStringEval(mm.group(5), lines[i], "step")))
			else:
				raise ksp_compiler.ParseException(lines[i], "Incorrect parameters. Expected: START_INC(<name>, <start-num>, <step-num>)\n")
		# If any incremeter has ended, pop the last object off the array.
		elif line == "END_INC":
			lines[i].command = ""
			iterObjs.pop()
		# If there are any iterators active, scan the line and replace occurances of the name with it's value.
		elif iterObjs:
			for iterationObj in iterObjs:
				mm = re.search(r"\b%s\b" % iterationObj.name, line)
				if mm:
					lines[i].command = re.sub(r"\b%s\b" % iterationObj.name, str(iterationObj.iterationVal), lines[i].command)
					iterationObj.increaseVal()

#=================================================================================================
class ArrayConcat(object):
	def __init__(self, arrayToFill, declare, brackets, size, arraysToConcat, line):
		self.line = line
		self.arrayToFill = arrayToFill
		self.declare = declare
		self.size = size
		self.brackets = brackets
		self.arraysToConcat = arraysToConcat.split(",")

	def checkArraySize(self, origLineIdx, lines):
		""" If the concat function is used on a declared empty size array, the size of the array needs to be calculated. """
		if self.declare:
			if not self.brackets:
				raise ksp_compiler.ParseException(self.line, "No array size given. Leave brackets [] empty to have the size auto generated.\n")
			elif not self.size:
				def findArrays():
					""" Scan through the lines up to this point to find all the the arrays that have been chosen to be concatenated,
					and from these add their number of elements to determine the total size needed. """
					sizes = []
					arrayNameList = list(self.arraysToConcat)
					for i in range(origLineIdx):
						lineText = lines[i].command.strip()
						if lineText.startswith("declare"):
							for arr in arrayNameList:
								try: # The regex doesn't like it when there are [] or () in the arr list.
									mm = re.search(r"^declare\s+%s?%s\s*(\[.*\])" % (varPrefixRe, arr.strip()), lineText)
									if mm:
										sizes.append(mm.group(1))
										arrayNameList.remove(arr)
										break
								except:
									raise ksp_compiler.ParseException(lines[i], "Syntax error.\n")
					if arrayNameList:  # If everything was found, then the list will be empty.
						raise ksp_compiler.ParseException(self.line, "Undeclared array(s) in %s function: %s\n" % (concatSyntax, ', '.join(arrayNameList).strip()))
					return(simplfyAdditionString(re.sub(r"[\[\]]", "", '+'.join(sizes))))
				self.size = findArrays()

	def getRawArrayDeclaration(self):
		""" Return the command that should replace line that triggered the concat. """
		return("declare %s[%s]" % (self.arrayToFill, str(self.size)))

	def buildLines(self):
		""" Return all the lines needed to perfrom the concat. """
		newLines = collections.deque()
		numArgs = len(self.arraysToConcat)

		offsets = ["0"]
		offsets.extend(["num_elements(%s)" % arrName for arrName in self.arraysToConcat])

		addOffset = ""
		if numArgs != 1:
			addOffset = " + concat_offset"
			newLines.append(self.line.copy("concat_offset := 0"))

		offsetCommand = "concat_offset := concat_offset + #offset#"
		templateText = [
		"for concat_it := 0 to num_elements(#arg#) - 1",
		"   #parent#[concat_it%s] := #arg#[concat_it]" % addOffset,
		"end for"]

		for j in range(numArgs):
			if j != 0 and numArgs != 1:
				newLines.append(self.line.copy(offsetCommand.replace("#offset#", offsets[j])))
			for text in templateText:
				newLines.append(self.line.copy(text.replace("#arg#", self.arraysToConcat[j]).replace("#parent#", self.arrayToFill)))
		return(newLines)

def handleArrayConcat(lines):
	arrayConcatRe = r"(?P<declare>^\s*declare\s+)?%s\s*(?P<brackets>\[(?P<arraysize>.*)\])?\s*:=\s*%s\s*\((?P<arraylist>[^\)]*)" % (variableNameRe, concatSyntax)
	newLines = collections.deque()
	for lineIdx in range(len(lines)):
		line = lines[lineIdx].command.strip()
		if "concat" in line:
			m = re.search(arrayConcatRe, line)
			if m:
				concatObj = ArrayConcat(m.group("whole"), m.group("declare"), m.group("brackets"), m.group("arraysize"), m.group("arraylist"), lines[lineIdx])
				concatObj.checkArraySize(lineIdx, lines)
				if m.group("declare"):
					newLines.append(lines[lineIdx].copy(concatObj.getRawArrayDeclaration()))
				newLines.extend(concatObj.buildLines())
				continue
		# The variables needed are declared at the start of the init callback.
		elif line.startswith("on"):
			if re.search(initRe, line):
				newLines.append(lines[lineIdx])
				newLines.append(lines[lineIdx].copy("declare concat_it"))
				newLines.append(lines[lineIdx].copy("declare concat_offset"))
				continue
		newLines.append(lines[lineIdx])
	replaceLines(lines, newLines)

#=================================================================================================
class MultiDimensionalArray(object):
	def __init__(self, name, prefix, dimensionsString, persistence, assignment, familyPrefix, line):
		self.name = name
		self.prefix = prefix or ""
		self.assignment = assignment or ""
		self.dimensions = ksp_compiler.split_args(dimensionsString, line)
		self.persistence = persistence or ""
		self.rawArrayName = familyPrefix + "_" + self.name

	def getRawArrayDeclaration(self):
		newName = self.prefix + "_" + self.name
		totalArraySize = "*".join(["(" + dim + ")" for dim in self.dimensions])
		return("declare %s %s [%s] %s" % (self.persistence, newName, totalArraySize, self.assignment))

	def buildPropertyAndConstants(self, line):
		propertyTemplate = [
		"property #propName#",
			"function get(#dimList#) -> result",
				"result := #rawArrayName#[#calculatedDimList#]",
			"end function",
			"function set(#dimList#, val)",
				"#rawArrayName#[#calculatedDimList#] := val",
			"end function ",
		"end property"]
		constTemplate = "declare const #name#.SIZE_D#dimNum# := #val#"

		newLines = collections.deque()
		# Build the declare const lines and add them to the newLines deque.
		for dimNum, dimSize in enumerate(self.dimensions):
			declareConstText = constTemplate\
				.replace("#name#", self.name)\
				.replace("#dimNum#", str(dimNum + 1))\
				.replace("#val#", dimSize)
			newLines.append(line.copy(declareConstText))
		# Build the list of arguments, eg: "d1, d2, d3"
		dimensionArgList = ["d" + str(dimNum + 1) for dimNum in range(len(self.dimensions))]
		dimensionArgString = ",".join(dimensionArgList)
		# Create the maths for mapping multiple dimensions to a single dimension array, eg: "d1 * (20) + d2"
		numDimensions = len(self.dimensions)
		calculatedDimList = []
		for dimNum in range(numDimensions - 1):
			for i in range(numDimensions - 1, dimNum, -1):
				calculatedDimList.append("(%s) * " % self.dimensions[i])
			calculatedDimList.append(dimensionArgList[dimNum] + " + ")
		calculatedDimList.append(dimensionArgList[numDimensions - 1])
		calculatedDimensions = "".join(calculatedDimList)
		for propLine in propertyTemplate:
			propertyText = propLine\
				.replace("#propName#", self.name)\
				.replace("#dimList#", dimensionArgString)\
				.replace("#rawArrayName#", self.rawArrayName)\
				.replace("#calculatedDimList#", calculatedDimensions)
			newLines.append(line.copy(propertyText))
		return(newLines)

# TODO: Check whether making this only init callback is ok.
def handleMultidimensionalArrays(lines):
	multipleDimensionsRe = r"\[(?P<dimensions>[^\]]+(?:\,[^\]]+)+)\]" # Match square brackets with 2 or more comma separated dimensions.
	multidimensionalArrayRe = r"^declare\s+%s%s\s*%s(?P<assignment>\s*:=.+)?$" % (persistenceRe, variableNameRe, multipleDimensionsRe)

	newLines = collections.deque()
	famCount = 0
	initFlag = False
	for lineIdx in range(len(lines)):
		line = lines[lineIdx].command.strip()
		if not initFlag:
			if re.search(initRe, line):
				initFlag = True
			newLines.append(lines[lineIdx])
		else: # Multidimensional arrays are only allowed in the init callback.
			if re.search(endOnRe, line):
				newLines.extend(lines[lineIdx:])
				break
			else:
				# If a multidim array is found, if necessary the family prefix is added and the lines needed for the property are added.
				famCount = countFamily(line, famCount)
				if line.startswith("declare"):
					m = re.search(multidimensionalArrayRe, line)
					if m:
						famPrefix = ""
						if famCount != 0:
							famPrefix = inspectFamilyState(lines, lineIdx)
						name = m.group("name")
						# if m.group("uiArray"):
						# 	name = name[1:] # If it is a UI array, the single dimension array will already have the underscore, so it is removed.
						multiDim = MultiDimensionalArray(name, m.group("prefix"), m.group("dimensions"), m.group("persistence"), m.group("assignment"), famPrefix, lines[lineIdx])
						newLines.append(lines[lineIdx].copy(multiDim.getRawArrayDeclaration()))
						newLines.extend(multiDim.buildPropertyAndConstants(lines[lineIdx]))
					else:
						newLines.append(lines[lineIdx])
				else:
					newLines.append(lines[lineIdx])

	replaceLines(lines, newLines)

#===========================================================================================
class UIPropertyTemplate:
	def __init__(self, name, argString):
		self.name = name
		self.args = argString.replace(" ", "").split(",")

class UIPropertyFunction:
	def __init__(self, functionType, args, line):
		self.functionType = functionType
		self.args  = args[1:]
		if len(self.args) > len(functionType.args):
			raise ksp_compiler.ParseException(line, "Too many arguments, maximum is %d, got %d.\n" % (len(functionType.args), len(self.args)))
		elif len(self.args) == 0:
			raise ksp_compiler.ParseException(line, "Function requires at least 2 arguments.\n")
		self.uiId = args[0]

	def buildUiPropertyLines(self, line):
		""" Return the set ui property commands, e.g. name -> par := val """
		newLines = collections.deque()
		for argNum in range(len(self.args)):
			newLines.append(line.copy("%s -> %s := %s" % (self.uiId, self.functionType.args[argNum], self.args[argNum])))
		return(newLines)

def handleUIFunctions(lines):
	# Templates for the functions. Note the ui-id as the first arg and the functions start
	# with'set_' is assumed to be true later on.
	uiControlPropertyFunctionTemplates = [
	"set_bounds(ui-id, x, y, width, height)",
	"set_slider_properties(ui-id, default, picture, mouse_behaviour)",
	"set_switch_properties(ui-id, text, picture, text_alignment, font_type, textpos_y)",
	"set_label_properties(ui-id, text, picture, text_alignment, font_type, textpos_y)",
	"set_menu_properties(ui-id, picture, font_type, text_alignment, textpos_y)",
	"set_table_properties(ui-id, bar_color, zero_line_color)",
	"set_button_properties(ui-id, text, picture, text_alignment, font_type, textpos_y)",
	"set_level_meter_properties(ui-id, bg_color, off_color, on_color, overload_color)",
	"set_waveform_properties(ui-id, bar_color, zero_line_color)",
	"set_knob_properties(ui-id, text, default)" ]

	# Use the template string above to build a list of UIProperyTemplate objects.
	uiFuncs = []
	for funcTemplate in uiControlPropertyFunctionTemplates:
		m = re.search(r"^(?P<name>[^\(]+)\(ui-id,(?P<args>[^\)]+)", funcTemplate)
		uiFuncs.append(UIPropertyTemplate(m.group("name"), m.group("args")))

	newLines = collections.deque()
	for lineIdx in range(len(lines)):
		line = lines[lineIdx].command.strip()
		foundProp = False
		if line.startswith("set_"):
			for func in uiFuncs:
				if re.search(r"^%s\b" % func.name, line):
					foundProp = True
					paramString = line[line.find("(") + 1 : len(line) - 1].strip()
					paramList = ksp_compiler.split_args(paramString, lines[lineIdx]) #re.split(commas_not_in_parenth, paramString)
					uiPropertyObj = UIPropertyFunction(func, paramList, lines[lineIdx])
					newLines.extend(uiPropertyObj.buildUiPropertyLines(lines[lineIdx]))
					break
		if not foundProp:
			newLines.append(lines[lineIdx])

	replaceLines(lines, newLines)

#=================================================================================================
def handleSameLineDeclaration(lines):
	""" When a variable is declared and initialised on the same line, check to see if the value needs to be
	moved over to the next line. """
	newLines = collections.deque()
	famCount = 0
	for lineIdx in range(len(lines)):
		line = lines[lineIdx].command.strip()
		famCount = countFamily(line, famCount)
		if line.startswith("declare"):
			m = re.search(r"^declare\s+(?:(polyphonic|global|local)\s+)*%s%s\s*:=" % (persistenceRe, variableNameRe), line)
			if m and not re.search(r"\b%s\s*\(" % concatSyntax, line):
				valueIsConstantInteger = False
				value = line[line.find(":=") + 2 :]
				if not re.search(stringOrPlaceholderRe, line):
					try:
						# Ideally this would check to see if the value is a Kontakt constant as those are valid
						# inline as well...
						eval(value) # Just used as a test to see if the the value is a constant.
						valueIsConstantInteger = True
					except:
						pass

				if not valueIsConstantInteger:
					preAssignmentText = line[: line.find(":=")]
					variableName = m.group("name")
					if famCount != 0:
						variableName = inspectFamilyState(lines, lineIdx) + variableName
					newLines.append(lines[lineIdx].copy(preAssignmentText))
					newLines.append(lines[lineIdx].copy(variableName + " " + line[line.find(":=") :]))
					continue
		newLines.append(lines[lineIdx])
	replaceLines(lines, newLines)

#=================================================================================================
class ConstBlock(object):
	def __init__(self, name):
		self.name = name
		self.memberValues = []
		self.memberNames = []
		self.previousVal = "-1"

	def addMember(self, name, value):
		""" Add a constant number """
		self.memberNames.append(name)
		newVal = value
		if not value:
			newVal = self.previousVal + "+1"
		newVal = simplfyAdditionString(newVal)
		self.memberValues.append(newVal)
		self.previousVal = newVal

	def buildLines(self, line):
		""" Return the the commands for the whole const block. """
		newLines = collections.deque()
		newLines.append(line.copy("declare %s[%s] := (%s)" % (self.name, len(self.memberNames), ", ".join(self.memberValues))))
		newLines.append(line.copy("declare const %s.SIZE := %s" % (self.name, len(self.memberNames))))
		for memNum in range(len(self.memberNames)):
			newLines.append(line.copy("declare const %s.%s := %s" % (self.name, self.memberNames[memNum], self.memberValues[memNum])))
		return(newLines)

def handleConstBlock(lines):
	constBlockStartRe = r"^const\s+%s$" % variableNameRe
	constBlockEndRe = r"^end\s+const$"
	constBlockMemberRe = r"^%s(?:$|\s*\:=\s*(?P<value>.+))" % variableNameRe

	newLines = collections.deque()
	constBlockObj = None
	inConstBlock = False
	for lineIdx in range(len(lines)):
		line = lines[lineIdx].command.strip()
		if line.startswith("const"):
			m = re.search(constBlockStartRe, line)
			if m:
				constBlockObj = ConstBlock(m.group("name"))
				inConstBlock = True
				continue
		elif line.startswith("end"):
			if re.search(constBlockEndRe, line):
				if constBlockObj.memberValues:
					newLines.extend(constBlockObj.buildLines(lines[lineIdx]))
				inConstBlock = False
				continue
		elif inConstBlock:
			m = re.search(constBlockMemberRe, line)
			if m:
				constBlockObj.addMember(m.group("whole"), m.group("value"))
				continue
			elif not line.strip() == "":
				raise ksp_compiler.ParseException(lines[lineIdx], "Incorrect syntax. In a const block, list constant names and optionally assign them a constant value.")
		newLines.append(lines[lineIdx])
	replaceLines(lines, newLines)

#=================================================================================================
class ListBlock(object):
	def __init__(self, name, size):
		self.name = name
		self.size = size or ""
		self.isMultiDim = False
		if size:
			self.isMultiDim = "," in size
		self.members = []

	def addMember(self, command):
		self.members.append(command)

	def buildLines(self, line):
		""" The list block just builds lines ready for the list function later on to interpret them. """
		newLines = collections.deque()
		newLines.append(line.copy("declare list %s[%s]" % (self.name, self.size)))
		for memNum in range(len(self.members)):
			memberName = self.members[memNum]
			# If the member is a comma separated list, then we first need to assign the list to an array in kontakt.
			if self.isMultiDim:
				# stringList = re.search(commasNotInBrackets, memberName)
				stringList = ksp_compiler.split_args(memberName, line)
				if len(stringList) != 1:
					memberName = self.name + str(memNum)
					newLines.append(line.copy("declare %s[] := (%s)" % (memberName, self.members[memNum])))
			newLines.append(line.copy("list_add(%s, %s)" % (self.name, memberName)))
		return(newLines)

def handleListBlocks(lines):
	listBlockStartRe = r"^list\s*%s\s*(?:\[(?P<size>%s)?\])?$" % (variableNameRe, variableOrInt)
	listBlockEndRe = r"^end\s+list$"
	newLines = collections.deque()
	listBlockObj = None
	isListBlock = False
	for lineIdx in range(len(lines)):
		line = lines[lineIdx].command.strip()
		m = re.search(listBlockStartRe, line)
		if m:
			isListBlock = True
			listBlockObj = ListBlock(m.group("whole"), m.group("size"))
		elif isListBlock and not line == "":
			if re.search(listBlockEndRe, line):
				isListBlock = False
				if listBlockObj.members:
					newLines.extend(listBlockObj.buildLines(lines[lineIdx]))
			else:
				listBlockObj.addMember(line)
		else:
			newLines.append(lines[lineIdx])

	replaceLines(lines, newLines)

#=================================================================================================
class List(object):
	def __init__(self, name, prefix, persistence, isMatrix, familyPrefix):
		self.name = name
		if isMatrix:
			self.name = "_%s" % self.name
		self.noUnderscoreName = name
		self.prefix = prefix or ""
		self.persistence = persistence or ""
		self.isMatrix = isMatrix
		self.familyPrefix = familyPrefix or ""
		self.inc = "0"
		self.sizeList = [] # If this is a matrix, the sizes of each element are stored.

	def getListDeclaration(self, line):
		""" This function returns the lines for a list declaration. Because the size of the list caluated based on how
		many list_add() functions have been use, this function must be called after all list_add() are resolved. """
		newLines = collections.deque()
		if not self.isMatrix:
			newLines.append(line.copy("declare %s %s%s[%s]" % (self.persistence, self.prefix, self.name, self.inc)))
			newLines.append(line.copy("declare const %s.SIZE := %s" % (self.noUnderscoreName, self.inc)))
		else:
			listMatrixTemplate = [
			"declare #list#.sizes[#size#] := (#sizeList#)",
			"declare #list#.pos[#size#] := (#posList#)",
			"property #list#",
				"function get(d1, d2) -> result",
					"result := _#list#[#list#.pos[d1] + d2]",
				"end function",
				"function set(d1, d2, val)",
					"_#list#[#list#.pos[d1] + d2] := val",
				"end function",
			"end property"]

			newLines.append(line.copy("declare %s %s%s[%s]" % (self.persistence, self.prefix, self.name, self.inc)))
			newLines.append(line.copy("declare const %s.SIZE := %s" % (self.noUnderscoreName, len(self.sizeList))))

			sizeCounter = "0"
			posList = ["0"]
			for i in range(len(self.sizeList) - 1):
				sizeCounter = simplfyAdditionString("%s+%s" % (sizeCounter, self.sizeList[i]))
				posList.append(sizeCounter)
			for text in listMatrixTemplate:
				replacedText = text.replace("#list#", self.noUnderscoreName)\
					.replace("#sizeList#", ",".join(self.sizeList))\
					.replace("#posList#", ",".join(posList))\
					.replace("#size#", str(len(self.sizeList)))
				newLines.append(line.copy(replacedText))
		return(newLines)

	def increaseInc(self, value):
		self.inc = simplfyAdditionString("%s+%s" % (self.inc, str(value)))
		self.sizeList.append(str(value))

	def getListAddLine(self, value, line):
		""" Return the line for single list add command. """
		string = "%s[%s] := %s" % (self.familyPrefix + self.name, self.inc, value)
		self.increaseInc(1)
		return(line.copy(string))

	def getArrayListAddLines(self, value, line, arrayName, arraySize):
		""" This is called when an array is being added to a list with list_add. The lines necessary are returned. """
		newLines = collections.deque()
		addArrayToListTemplate = [
		"for list_it := 0 to #size# - 1",
			"#list#[list_it + #offset#] := #arr#[list_it]",
		"end for"]
		for templateLine in addArrayToListTemplate:
			text = templateLine.replace("#size#", arraySize)\
				.replace("#list#", self.familyPrefix + self.name)\
				.replace("#offset#", self.inc)\
				.replace("#arr#", arrayName)
			newLines.append(line.copy(text))
		self.increaseInc(arraySize)
		return(newLines)


def handleLists(lines):
	def findAllArrays(lines):
		""" Scan the all the lines and store arrays and their sizes. """
		arrayNames = []
		arraySizes = []
		initFlag = False
		for i in range(len(lines)):
			line = lines[i].command.strip()
			if initFlag == False:
				if line.startswith("on"):
					if re.search(initRe, line):
						initFlag = True
			else:
				if line.startswith("end"):
					if re.search(endOnRe, line):
						break
				if line.startswith("declare"):
					m = re.search(r"^declare\s+%s%s\s*(?:\[(%s)\])" % (persistenceRe, variableNameUnRe, variableOrInt), line)
					if m:
						arrayNames.append(re.sub(varPrefixRe, "", m.group(2)))
						arraySizes.append(m.group(5))
		return (arrayNames, arraySizes)
	# The names and sizes are needed because the multidimensional lists need to use the sizes to calculate the total.
	arrayNames, arraySizes = findAllArrays(lines)

	newLines = collections.deque()
	lists = {} # The list names and list objects are stored in a dict for quick searching.
	listAddRe = r"^list_add\s*\(\s*%s\s*,(?P<value>.+)\)$" % variableNameRe
	listDeclareRe = r"^\s*declare\s+%slist\s*%s\s*(?:\[(?P<size>[^\]]+)?\])?" % (persistenceRe, variableNameRe)
	listDeclareTag = "LIST=>" # A tag is left on the list declaration lines as these need to be resolved at the end.
	isInInit = False
	preInit = True
	addInitVar = False
	loopBlockCounter = 0
	famCount = 0
	for lineIdx in range(len(lines)):
		line = lines[lineIdx].command.strip()
		if isInInit == False:
			if preInit:
				if line.startswith("on"):
					if re.search(initRe, line):
						preInit = False
						isInInit = True
						addInitVar = True
			if line.startswith("list_add"):
				if re.search(listAddRe, line):
					raise ksp_compiler.ParseException(lines[lineIdx], "list_add() can only be used in the init callback.\n")
			newLines.append(lines[lineIdx])
			if addInitVar:
				newLines.append(lines[lineIdx].copy("declare list_it"))
				addInitVar = False
			continue
		else:
			# Check for the end of the init callback
			if line.startswith("end"):
				if re.search(endOnRe, line):
					isInInit = False
					newLines.append(lines[lineIdx])
					continue

			def findLoop(lineText, loopCount):
				""" Check for any fors, whiles or ifs. This is layed out in this fashion for speed reasons. """
				startVal = loopCount
				if lineText.startswith("for"):
					if re.search(forRe, lineText):
						loopCount += 1
				elif lineText.startswith("while"):
					if re.search(whileRe, lineText):
						loopCount += 1
				elif lineText.startswith("if"):
					if re.search(ifRe, lineText):
						loopCount += 1
				elif loopCount != 0:
					if lineText.startswith("end"):
						if re.search(endForRe, lineText):
							loopCount -= 1
						elif re.search(endIfRe, lineText):
							loopCount -= 1
						elif re.search(endWhileRe, lineText):
							loopCount -= 1
				return(loopCount, startVal != loopCount)
			shouldExit = False
			loopBlockCounter, shouldExit = findLoop(line, loopBlockCounter)
			if shouldExit:
				newLines.append(lines[lineIdx])
				continue

			famCount = countFamily(line, famCount)
			# Check for a list declaration
			if line.startswith("declare"):
				m = re.search(listDeclareRe, line)
				if m:
					name = m.group("name")
					famPre = ""
					if famCount != 0:
						famPre = inspectFamilyState(lines, lineIdx)
					isMatrix = False
					if m.group("size"):
						isMatrix = "," in m.group("size")
					listObj = List(name, m.group("prefix"), m.group("persistence"), isMatrix, famPre)
					name = "%s%s" % (famPre, name)
					lists[name] = listObj
					newLines.append(lines[lineIdx].copy("%s%s" % (listDeclareTag, name))) # Mark this line as we will need to go back and fill in the declaration later.
					continue

			# Check for a list_add
			elif line.startswith("list_add"):
				m = re.search(listAddRe, line)
				if m:
					# if loopBlockCounter != 0:
					# 	raise ksp_compiler.ParseException(lines[lineIdx], "list_add() cannot be used in loops or if statements.\n")
					name = m.group("name")
					value = m.group("value").strip()
					try:
						listObj = lists[name]
					except KeyError:
						raise ksp_compiler.ParseException(lines[lineIdx], "Undeclared list: %s\n" % name)
					if listObj.isMatrix:
						try:
							arrayIdx = arrayNames.index(re.sub(varPrefixRe, "", value))
							newLines.extend(listObj.getArrayListAddLines(value, lines[lineIdx], arrayNames[arrayIdx], arraySizes[arrayIdx]))
						except ValueError:
							newLines.append(listObj.getListAddLine(value, lines[lineIdx]))
							pass
					else:
						newLines.append(listObj.getListAddLine(value, lines[lineIdx]))
					continue
		newLines.append(lines[lineIdx])

	# Replace the list declartion tags with the actual values.
	newerLines = collections.deque()
	for line in newLines:
		if line.command.startswith(listDeclareTag):
			listObj = lists[line.command[len(listDeclareTag) :]]
			if listObj.inc != "0":
				newerLines.extend(lists[line.command[len(listDeclareTag) :]].getListDeclaration(line))
		else:
			newerLines.append(line)

	replaceLines(lines, newerLines)

#=================================================================================================
def handleOpenSizeArrays(lines):
	""" When an array size is left with an open number of elements, use the list of initialisers to provide the array size.
	Const variables are also generated for the array size. """
	openArrayRe = r"^\s*declare\s+%s%s\s*\[\s*\]\s*:=\s*\(" % (persistenceRe, variableNameRe)
	newLines = collections.deque()
	for lineIdx in range(len(lines)):
		line = lines[lineIdx].command.strip()
		m = re.search(openArrayRe, line)
		if m:
			stringList = re.split(commasNotInBrackets, line[line.find("(") + 1 : len(line) - 1])
			numElements = len(stringList)
			name = m.group("name")
			newLines.append(lines[lineIdx].copy(line[: line.find("[") + 1] + str(numElements) + line[line.find("[") + 1 :]))
			newLines.append(lines[lineIdx].copy("declare const %s.SIZE := %s" % (name, str(numElements))))
		else:
			newLines.append(lines[lineIdx])
	replaceLines(lines, newLines)

#=================================================================================================
def handleStringArrayInitialisation(lines):
	""" Convert the single-line list of strings to one string per line for Kontakt to understand. """
	stringArrayRe = r"^declare\s+%s\s*\[(?P<arraysize>[^\]]+)\]\s*:=\s*\((?P<initlist>.+)\)$" % variableNameRe
	stringListRe = r"\s*%s(\s*,\s*%s)*\s*" % (stringOrPlaceholderRe, stringOrPlaceholderRe)
	newLines = collections.deque()
	famCount = 0
	for i in range(len(lines)):
		line = lines[i].command.strip()
		famCount = countFamily(line, famCount)
		if line.startswith("on"):
			if re.search(initRe, line):
				newLines.append(lines[i])
				newLines.append(lines[i].copy("declare string_it"))
				continue
		if line.startswith("declare"):
			m = re.search(stringArrayRe, line)
			if m:
				if m.group("prefix") == "!":
					if not re.search(stringListRe, m.group("initlist")):
						raise ksp_compiler.ParseException(lines[i], "Expected integers, got strings.\n")
					stringList = ksp_compiler.split_args(m.group("initlist"), lines[i])
					name = m.group("name")
					if famCount != 0:
						name = inspectFamilyState(lines, i) + name
					newLines.append(lines[i].copy(line[: line.find(":")]))
					if len(stringList) != 1:
						for ii in range(len(stringList)):
							newLines.append(lines[i].copy("%s[%s] := %s" % (name, str(ii), stringList[ii])))
					else:
						newLines.append(lines[i].copy("for string_it := 0 to %s - 1" % m.group("arraysize")))
						newLines.append(lines[i].copy("%s[string_it] := %s" % (name, "".join(stringList))))
						newLines.append(lines[i].copy("end for"))
					continue
		newLines.append(lines[i])
	replaceLines(lines, newLines)

#=================================================================================================
def handlePersistence(lines):
	""" Simple adds make_persistent() or read_perisitent_var() lines when the pers or read keywords are found. """
	newLines = collections.deque()
	famCount = 0
	for i in range(len(lines)):
		line = lines[i].command.strip()
		famCount = countFamily(line, famCount)
		if line.startswith("declare"):
			# The name of the variable is assumed to either be the first word before a [ or ( or before the end of the line
			m = re.search(r"\b(?P<persistence>pers|instpers|read)\b" , line)
			if m:
				persWord = m.group("persistence")
				m = re.search(nameInDeclareStmtRe, line)
				if m:
					variableName = m.group("name")
					if famCount != 0: # Counting the family state is much faster than inspecting on every line.
						famPre = inspectFamilyState(lines, i)
						if famPre:
							variableName = famPre + variableName.strip()
					newLines.append(lines[i].copy(re.sub(r"\b%s\b" % persWord, "", line)))
					if persWord == "pers":
						newLines.append(lines[i].copy("make_persistent(%s)" % variableName))
					if persWord == "instpers":
						newLines.append(lines[i].copy("make_instr_persistent(%s)" % variableName))
					if persWord == "read":
						newLines.append(lines[i].copy("make_persistent(%s)" % variableName))
						newLines.append(lines[i].copy("read_persistent_var(%s)" % variableName))
					continue
		newLines.append(lines[i])

	replaceLines(lines, newLines)

#=================================================================================================
class IterateMacro(object):
	def __init__(self, macroName, minVal, maxVal, step, direction, line):
		self.line = line
		self.macroName = macroName
		self.isSingleLine = "#n#" in self.macroName
		self.minVal = int(tryStringEval(minVal, line, "min"))
		self.maxVal = int(tryStringEval(maxVal, line, "max"))
		self.step = 1
		if step:
			self.step = int(tryStringEval(step, line, "step"))
		self.direction = direction
		if (self.minVal > self.maxVal and self.direction == "to") or (self.minVal < self.maxVal and self.direction == "downto"):
			raise ksp_compiler.ParseException(line, "Min and max values are incorrectly weighted (For example, min > max when it should be min < max).\n")

	def buildLines(self):
		newLines = collections.deque()
		offset = 1
		if self.direction == "downto":
			self.step = -self.step
			offset = -1

		if not self.isSingleLine:
			for i in range(self.minVal, self.maxVal + offset, self.step):
				newLines.append(self.line.copy("%s(%s)" % (self.macroName, str(i))))
		else:
			for i in range(self.minVal, self.maxVal + offset, self.step):
				newLines.append(self.line.copy(self.macroName.replace("#n#", str(i))))
		return(newLines)

def handleIterateMacro(lines):
	scan = False
	newLines = collections.deque()
	for lineIdx in range(len(lines)):
		line = lines[lineIdx].command.strip()
		if line.startswith("iterate_macro"):
			scan = True
			m = re.search(r"^iterate_macro\s*\((?P<macro>.+)\)\s*:=\s*(?P<min>.+)\b(?P<direction>to|downto)(?P<max>(?:.(?!\bstep\b))+)(?:\s+step\s+(?P<step>.+))?$", line)
			if m:
				iterateObj = IterateMacro(m.group("macro"), m.group("min"), m.group("max"), m.group("step"), m.group("direction"), lines[lineIdx])
				newLines.extend(iterateObj.buildLines())
			else:
				newLines.append(lines[lineIdx])
		else:
			newLines.append(lines[lineIdx])
	replaceLines(lines, newLines)

	return scan

#=================================================================================================
class DefineConstant(object):
	def __init__(self, name, value, argString, line):
		self.name = name
		self.value = value
		# In previous versions of the compiler the value had to wrapped in # symbols.
		if self.value.startswith("#") and self.value.endswith("#") and not "#" in self.value[1 : len(self.value) - 1]:
			self.value = self.value[1 : len(self.value) - 1]
		self.args = []
		if argString:
			self.args = ksp_compiler.split_args(argString, line)
		self.line = line
		if re.search(r"\b%s\b" % self.name, self.value):
			raise ksp_compiler.ParseException(self.line, "Define constant cannot call itself.")

	def getName(self):
		return(self.name)
	def getValue(self):
		return(self.value)
	def setValue(self, val):
		self.value = val

	def evaluateValue(self):
		# Try to evaluate the value of the define constant as a maths expression.
		# But don't do it if the define value is a string (starting with ")!
		newVal = self.value

		nonMath = ["\"", "\'"]
		if not any(s in newVal for s in nonMath):
			try:
				val = re.sub(r"\bmod\b", "%", self.value)
				newVal = str(stringEvaluator.eval(val))
			except:
				pass
		self.setValue(newVal)

	def substituteValue(self, command, listOfOtherDefines, line=None):
		""" Replace all occurances of the define constant in the given command with its value. """
		newCommand = command
		if self.name in command:
			if not self.args:
				newCommand = re.sub(r"\b%s\b" % self.name, self.value, command)
			else:
				lineObj = line or self.line
				matchIt = re.finditer(r"\b%s\b" % self.name, command)
				for match in matchIt:
					# Parse the match
					matchPos = match.start()
					parenthCount = 0
					preBracketFlag = True # Flag to show when the first bracket is found.
					foundString = []
					for char in command[matchPos:]:
						if char == "(":
							parenthCount += 1
							preBracketFlag = False
						elif char == ")":
							parenthCount -= 1
						foundString.append(char)
						if parenthCount == 0 and preBracketFlag == False:
							break
					foundString = "".join(foundString)

					# Check whether the args are valid
					openBracketPos = foundString.find("(")
					if openBracketPos == -1:
						raise ksp_compiler.ParseException(lineObj, "No arguments found for define macro: %s" % foundString)
					argsString = foundString[openBracketPos + 1 : len(foundString) - 1]
					foundArgs = ksp_compiler.split_args(argsString, lineObj)
					if len(foundArgs) != len(self.args):
						# The number of args could be incorrect because there are other defines in the arg list, therefore first evaluate
						# all other defines in the args. If still incorrect, raise an exception.
						for defineObj in listOfOtherDefines:
							argsString = defineObj.substituteValue(argsString, listOfOtherDefines)
						foundArgs = ksp_compiler.split_args(argsString, lineObj)
						if len(foundArgs) != len(self.args):
							raise ksp_compiler.ParseException(lineObj, "Incorrect number of arguments in define macro: %s. Expected %d, got %d.\n" % (foundString, len(self.args), len(foundArgs)))

					# Build the new value using the given args
					newVal = self.value
					for argIdx, arg in enumerate(self.args):
						if arg.startswith("#") and arg.endswith("#"):
							newVal = re.sub(arg, foundArgs[argIdx], newVal)
						else:
							newVal = re.sub(r"\b%s\b" % arg, foundArgs[argIdx], newVal)
					newCommand = newCommand.replace(foundString, newVal)
		return(newCommand)

def handleDefineConstants(lines):
	defineRe = r"^define\s+%s\s*(?:\((?P<args>.+)\))?\s*:=(?P<val>.+)$" % variableNameRe
	defineConstants = collections.deque()
	newLines = collections.deque()

	# Scan through all the lines to find define declarations.
	for lineIdx in range(len(lines)):
		line = lines[lineIdx].command.strip()
		if line.startswith("define"):
			m = re.search(defineRe, line)
			if m:
				defineObj = DefineConstant(m.group("whole"), m.group("val").strip(), m.group("args"), lines[lineIdx])
				defineConstants.append(defineObj)
				continue
		newLines.append(lines[lineIdx])

	if defineConstants:
		# Replace all occurances where other defines are used in define values.
		for i in range(len(defineConstants)):
			for j in range(len(defineConstants)):
				defineConstants[i].setValue(defineConstants[j].substituteValue(defineConstants[i].getValue(), defineConstants))
			defineConstants[i].evaluateValue()

		# For each line, replace any places the defines are used.
		for lineIdx in range(len(newLines)):
			line = newLines[lineIdx].command
			for defineConst in defineConstants:
				newLines[lineIdx].command = defineConst.substituteValue(newLines[lineIdx].command, defineConstants, newLines[lineIdx])
	replaceLines(lines, newLines)

def createBuiltinDefines(lines):
	# Create date-time variables

	timecodes = ['%S', '%M', '%H', '%I', '%p', '%d', '%m', '%Y', '%y', '%B', '%b', '%x', '%X']
	timenames = ['__SEC__','__MIN__','__HOUR__','__HOUR12__','__AMPM__','__DAY__','__MONTH__','__YEAR__','__YEAR2__','__LOCALE_MONTH__','__LOCALE_MONTH_ABBR__','__LOCALE_DATE__','__LOCALE_TIME__']
	defines = ['define {0} := \"{1}\"'.format(timenames[i], strftime(timecodes[i], localtime())) for i in range(len(timecodes))]
	
	newLines = collections.deque()

	# append our defines on top of the script in a temporary deque
	for string in defines:
		newLines.append(lines[0].copy(string))

	# merge with the original unmodified script
	for line in lines:
		newLines.append(line)

	# replace original deque with modified one
	replaceLines(lines, newLines)

#=================================================================================================
class UIArray(object):
	def __init__(self, name, uiType, size, persistence, familyPrefix, uiParams, tableSize, prefixSymbol, line):
		self.name = name
		self.familyPrefix = familyPrefix or ""
		self.uiType = uiType
		self.prefixSymbol = prefixSymbol
		if self.uiType == "ui_text_edit":
			self.prefixSymbol = "@"
		self.uiParams = uiParams or ""
		self.numElements = size
		self.dimensionsString = size
		self.underscore = ""
		if "," in size:
			self.underscore = "_"
			self.numElements = "*".join(["(%s)" % dim for dim in size.split(",")])
		self.numElements = tryStringEval(self.numElements, line, "UI array size")
		self.persistence = persistence or ""
		self.tableSize = tableSize

	def getRawArrayDeclaration(self):
		""" Get the command string for declaring the raw ID array. """
		return("declare %s[%s]" % (self.name, self.dimensionsString))

	def buildLines(self, line):
		""" Return the deque of lines for the ui declaration (just a load of declare ui and get_ui_id()). """
		newLines = collections.deque()
		for i in range(self.numElements):
			uiName = self.underscore + self.name
			if self.uiType == "ui_table" or self.uiType == "ui_xy":
				text = "declare %s %s %s %s" % (self.persistence, self.uiType, self.prefixSymbol + uiName + str(i), self.tableSize + self.uiParams)
			else:
				text = "declare %s %s %s %s" % (self.persistence, self.uiType, self.prefixSymbol + uiName + str(i), self.uiParams)
			newLines.append(line.copy(text))
			text = "%s[%s] := get_ui_id(%s)" % (self.familyPrefix + uiName, str(i), self.familyPrefix + uiName + str(i))
			newLines.append(line.copy(text))
		return(newLines)

def handleUIArrays(lines):
	uiTypeRe = r"\b(?P<uitype>ui_\w*)\b"
	uiArrayRe = r"^declare\s+%s%s\s+%s\s*\[(?P<arraysize>[^\]]+)\]\s*(?P<tablesize>\[[^\]]+\]\s*)?(?P<uiparams>\(.*)?" % (persistenceRe, uiTypeRe, variableNameRe)
	newLines = collections.deque()
	famCount = 0
	for lineNum in range(len(lines)):
		line = lines[lineNum].command.strip()
		famCount = countFamily(line, famCount)
		if line.startswith("decl"):
			m = re.search(uiArrayRe, line)
			if m:
				uiType = m.group("uitype")
				famPre = None
				if famCount != 0:
					famPre = inspectFamilyState(lines, lineNum)
				if ((uiType == "ui_table" or uiType == "ui_xy") and m.group("tablesize")) or (uiType != "ui_table" and uiType != "ui_xy"):
					arrayObj = UIArray(m.group("name"), uiType, m.group("arraysize"), m.group("persistence"), famPre, m.group("uiparams"), m.group("tablesize"), m.group("prefix"), lines[lineNum])
					newLines.append(lines[lineNum].copy(arrayObj.getRawArrayDeclaration()))
					newLines.extend(arrayObj.buildLines(lines[lineNum]))
					continue
		newLines.append(lines[lineNum])
	replaceLines(lines, newLines)

#=================================================================================================
def handleDefineLiterals(lines):
	""" Finds all define literals, and just replaces their occurances with the list of literals. """
	defineTitles = []
	defineValues = []
	defineLinePos = []
	for index in range(len(lines)):
		line = lines[index].command.strip()
		if line.startswith("define"):
			if re.search(r"^define\s+literals\s+", line):
				if re.search(r"^define\s+literals\s+" + variableNameUnRe + r"\s*:=", line):
					textWithoutDefine = re.sub(r"^define\s+literals\s*", "", line)
					colonBracketPos = textWithoutDefine.find(":=")

					# before the assign operator is the title
					title = textWithoutDefine[ : colonBracketPos].strip()
					defineTitles.append(title)

					# after the assign operator is the value
					value = textWithoutDefine[colonBracketPos + 2 : ].strip()
					m = re.search(r"^\((([a-zA-Z_][a-zA-Z0-9_.]*)?(\s*,\s*[a-zA-Z_][a-zA-Z0-9_.]*)*)\)$", value)
					if not m:
						raise ksp_compiler.ParseException(lines[index], "Syntax error in define literals: Comma separated identifier list in () expected.\n")

					value = m.group(1)
					value = ",".join([val.strip() for val in value.split(",")]) # remove whitespace
					defineValues.append(value)

					defineLinePos.append(index)
					# remove the line
					lines[index].command = re.sub(r'[^\r\n]', '', line)
				else:
					raise ksp_compiler.ParseException(lines[index], "Syntax error in define literals.\n")

	# if at least one define const exsists
	if defineTitles:
		# scan the code can replace any occurances of the variable with it's value
		for lineObj in lines:
			line = lineObj.command
			for index, item in enumerate(defineTitles):
				if re.search(r"\b" + item + r"\b", line):
					# character_before = line[line.find(item) - 1 : line.find(item)]
					# if character_before.isalpha() == False and character_before.isdiget() == False:
					lineObj.command = lineObj.command.replace(item, str(defineValues[index]))

#=================================================================================================
def handleLiterateMacro(lines):
	scan = False
	newLines = collections.deque()
	for lineIdx in range(len(lines)):
		line = lines[lineIdx].command.strip()
		if line.startswith("literate_macro"):
			scan = True
			m = re.search(r"^literate_macro\s*\((?P<macro>.+)\)\s+on\s+(?P<target>.+)$", line)
			if m:
				name = m.group("macro")
				targets = ksp_compiler.split_args(m.group("target"), lines[lineIdx])
				if not "#l#" in name:
					for text in targets:
						newLines.append(lines[lineIdx].copy("%s(%s)" % (name, text)))
				else:
					for text in targets:
						newLines.append(lines[lineIdx].copy(name.replace("#l#", text)))
				continue
		newLines.append(lines[lineIdx])
	replaceLines(lines, newLines)
	return scan