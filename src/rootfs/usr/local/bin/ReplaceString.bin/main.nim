import os, strutils

proc printHelp() =
  echo """
Nim String Replacer (Advanced)
------------------------------
Usage: 
  ./filename <direction>:<count> offset:<index> <original> <search> <replace>

Arguments:
  1. direction:count   "fromBeginning" or "fromEnd" followed by count (0 for all).
  2. offset:index      "offset" followed by the numeric start/end boundary.
  3. original          The source text.
  4. search            The substring to find.
  5. replace           The replacement string.

Example:
  ./filename fromBeginning:2 offset:0 "banana" "a" "o"
  # Result: "bonona" (Only the first two 'a's are replaced)
"""

proc main() =
  if paramCount() != 5:
    printHelp()
    return

  # Parse Arg 1: direction:count
  let arg1 = paramStr(1).split(':')
  if arg1.len != 2:
    printHelp()
    return
  
  let direction = arg1[0]
  let countLimit = try: parseInt(arg1[1]) except ValueError: -1

  # Parse Arg 2: offset:index
  let arg2 = paramStr(2).split(':')
  if arg2.len != 2 or arg2[0] != "offset":
    printHelp()
    return
  
  let offset = try: parseInt(arg2[1]) except ValueError: -1

  if countLimit < 0 or offset < 0:
    echo "Error: Count and Offset must be positive integers."
    return

  let original = paramStr(3)
  let search = paramStr(4)
  let replace = paramStr(5)

  if search == "":
    echo original
    return

  var result = original
  var matchesHandled = 0

  if direction == "fromBeginning":
    var currentPos = offset
    while (countLimit == 0 or matchesHandled < countLimit):
      let foundAt = result.find(search, currentPos)
      if foundAt == -1: break
      
      result.delete(foundAt, foundAt + search.len - 1)
      result.insert(replace, foundAt)
      
      # Move currentPos forward past the newly inserted string
      currentPos = foundAt + replace.len
      matchesHandled += 1

  elif direction == "fromEnd":
    var currentEnd = offset
    while (countLimit == 0 or matchesHandled < countLimit):
      # rfind searches backwards; 'last' is the highest index to check
      let foundAt = result.rfind(search, last = currentEnd)
      if foundAt == -1: break
      
      result.delete(foundAt, foundAt + search.len - 1)
      result.insert(replace, foundAt)
      
      # Move the boundary back before the match we just replaced
      currentEnd = foundAt - 1
      if currentEnd < 0: break
      matchesHandled += 1
  else:
    echo "Error: Direction must be 'fromBeginning' or 'fromEnd'."
    printHelp()
    return

  echo result

if isMainModule:
  main()