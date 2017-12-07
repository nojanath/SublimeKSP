import re
import collections

#=================================================================================================
def Main (lines):
	newLines = collections.deque()
	for lineIdx in range(len(lines)):
		line = lines[lineIdx].command.strip()
		if line.startswith("PredefineFunc"):
			assert (re.search(r"PredefineFunc.*?\(.*?\)",line)),"something is missed"
			m = re.search(r"PredefineFunc.*?\((.*?)\)",line)
			lines[lineIdx].command = '\n message("PredefineFunc"&'+ m.group(1) +')'
			print (lines[lineIdx])
		newLines.append(lines[lineIdx])
	return newLines