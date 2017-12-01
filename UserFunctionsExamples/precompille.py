import re
import collections

#=================================================================================================
def Main (lines):
	newLines = collections.deque()
	initstart = False
	insideinit = False
	placeline = False
	for lineIdx in range(len(lines)):
		line = lines[lineIdx].command.strip()
		if line.startswith("on init"):
			initstart = True
			placeline = True
			# newLines.extend (newline)
		if line.startswith("end on"):
			if initstart == True:
				initstart = False
				placeline = True
		if placeline == True:
			newLines.extend (buildLines(lines[lineIdx],initstart))
			placeline = False
		else:
			newLines.append(lines[lineIdx])
	return newLines

def buildLines(line,initstart):
	""" Return the the commands for the whole const block. """
	newLines = collections.deque()
	if initstart == True:
		newLines.append(line.copy('on init'))
		newLines.append(line.copy('message("INITSTART")'))
		newLines.append(line.copy('if (1=1)'))
	if initstart == False:
		newLines.append(line.copy('end if'))
		newLines.append(line.copy('message("INITEND")'))
		newLines.append(line.copy('end on'))
	
	return newLines