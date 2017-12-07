import preprocessor_plugins
import re
import collections
import ksp_compiler
import importlib
import sys

#=================================================================================================

class UserFuntions:
	'''	Class witch hanles custom user functions. __init__ removes any functions related to class from code	and imports user libraries
	UserPreDefine runs just in start of pre_macro_functions 
	UserPostDefine runs after define lines are removed and solved 
	UserPostMacro runs after iterate and literate macro are solved
	UserPreCompille runs after all preprocessor plugins before the magic starts'''

	PathDefined = False
	UserPreDefineUsed = False
	UserPostDefineUsed = False
	UserPostMacroUsed = False
	UserPreCompilleUsed = False
	Path = ""
	UserPreDefineName = ""
	UserPostDefineName = ""
	UserPostMacroName = ""
	UserPreCompilleName = ""


	def __init__ (self,lines):
		newLines = collections.deque()
		for lineIdx in range(len(lines)):
			line = lines[lineIdx].command.strip()
			if line.startswith("userlibs_path"):
				self.PathDefined = True
				assert (re.search(r".*?\(.*?\)",line)),"wrong argument. Use Syntax: userlibs_path(path). Do not use \'\' or \"\" "
				m = re.match(r".*?\((.*?)\)",line)
				if m:
					lines[lineIdx].command = " "
					self.Path = m.group(1)
			if line.startswith("import_predefine_lib"):
				assert (re.search(r".*?\(.*?\)",line)),"wrong arguments. Use Syntax: import_predefine_lib(name). Do not use \'\' or \"\" "
				self.UserPreDefineUsed = True
				m = re.match(r".*?\((.*?)\)",line)
				if m:
					lines[lineIdx].command = " "
					self.UserPreDefineName = m.group(1)
			if line.startswith("import_postdefine_lib"):
				assert (re.search(r".*?\(.*?\)",line)),"wrong arguments. Use Syntax: import_postdefine_lib(name). Do not use \'\' or \"\" "
				self.UserPostDefineUsed = True
				m = re.match(r".*?\((.*?)\)",line)
				if m:
					lines[lineIdx].command = " "
					self.UserPostDefineName = m.group(1)
			if line.startswith("import_postmacro_lib"):
				assert (re.search(r".*?\(.*?\)",line)),"wrong arguments. Use Syntax: import_postmacro_lib(name). Do not use \'\' or \"\" "
				self.UserPostMacroUsed = True
				m = re.match(r".*?\((.*?)\)",line)
				if m:
					lines[lineIdx].command = " "
					self.UserPostMacroName = m.group(1)
			if line.startswith("import_precompille_lib"):
				assert (re.search(r".*?\(.*?\)",line)),"wrong arguments. Use Syntax: import_precompille_lib(name). Do not use \'\' or \"\" "
				self.UserPreCompilleUsed = True
				m = re.match(r".*?\((.*?)\)",line)
				if m:
					lines[lineIdx].command = " "
					self.UserPreCompilleName = m.group(1)
			newLines.append(lines[lineIdx])
		if self.PathDefined == True:
			sys.path.append(self.Path)
			if self.UserPreDefineUsed == True:
				self.UserPreDefineLib = importlib.import_module(self.UserPreDefineName)
			if self.UserPostDefineUsed == True:
				self.UserPostDefineLib = importlib.import_module(self.UserPostDefineName)
			if self.UserPostMacroUsed == True:
				self.UserPostMacroLib = importlib.import_module(self.UserPostMacroName)
			if self.UserPreCompilleUsed == True:
				self.UserPreCompilleLib = importlib.import_module(self.UserPreCompilleName)

	def UserPreDefine (self,lines):
		if self.UserPreDefineUsed == True:
			assert (self.PathDefined == True), "Path for user libraries is not set. Use function: userlibs_path(path). Do not use \'\' or \"\" "
			PreDefineLines = self.UserPreDefineLib.Main(lines)
			preprocessor_plugins.replaceLines(lines, PreDefineLines)
			del PreDefineLines

	def UserPostDefine (self,lines):
		if self.UserPostDefineUsed == True:
			assert (self.PathDefined == True), "Path for user libraries is not set. Use function: userlibs_path(path). Do not use \'\' or \"\" "
			PostDefineLines = self.UserPostDefineLib.Main(lines)
			preprocessor_plugins.replaceLines(lines, PostDefineLines)
			del PostDefineLines

	def UserPostMacro (self,lines):
		if self.UserPostMacroUsed == True:
			assert (self.PathDefined == True), "Path for user libraries is not set. Use function: userlibs_path(path). Do not use \'\' or \"\" "
			PostMacroLines = self.UserPostMacroLib.Main(lines)
			preprocessor_plugins.replaceLines(lines, PostMacroLines)
			del PostMacroLines

	def UserPreCompille (self,lines):
		if self.UserPreCompilleUsed == True:
			assert (self.PathDefined == True), "Path for user libraries is not set. Use function: userlibs_path(path). Do not use \'\' or \"\" "
			PreCompilleLines = self.UserPreCompilleLib.Main(lines)
			preprocessor_plugins.replaceLines(lines, PreCompilleLines)
			del PreCompilleLines