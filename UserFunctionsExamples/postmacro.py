import re
import collections

#=================================================================================================
def Main (lines):
	newLines = collections.deque()
	count = 0
	
	for lineIdx in range(len(lines)):
		
		line = lines[lineIdx].command.strip()
		if line.startswith("PostMacro"):
			assert (re.search(r"PostMacro.*?\(.*?\d.*?\)",line)),"something is missed"
			count += 1
			m = re.search(r"PostMacro.*?\((.*?)\)",line)
			if m:
				lines[lineIdx].command = 'message("PostMacro inside value"&'+ m.group(1) +'& "outside value = " & '+ str(count) +')'
		newLines.append(lines[lineIdx])
	return newLines