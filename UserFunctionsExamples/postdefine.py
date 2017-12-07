import re
import collections

#=================================================================================================
def Main (lines):
	newLines = collections.deque()
	for lineIdx in range(len(lines)):
		line = lines[lineIdx].command.strip()
		if line.startswith("PostDefineFunc"):
			assert (re.search(r"PostDefineFunc.*?\(.*?\)",line)),"have to be numeric"
			m = re.search(r"PostDefineFunc.*?\((.*?)\)",line)
			lines[lineIdx].command = '\n message("PostDefineFunc"&'+ m.group(1) +')'
			print (lines[lineIdx])
		newLines.append(lines[lineIdx])
	return newLines