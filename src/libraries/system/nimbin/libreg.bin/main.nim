import os, strutils, tables, options, sequtils, uri, json, oids, osproc, posix

# ----------------------------
# Hive configuration (extensible)
# ----------------------------
const defaultLocalPath = ".local/aqua/registry"

var hiveMap = {
  "HKEY_LOCAL_MACHINE": "/opt/aqua/registry",
  "HKEY_CURRENT_USER": "$HOME/" & defaultLocalPath,
  "HKEY_VOLATILE_MEMORY": "/opt/aqua/vfs/registry",
  "HKEY_LOCAL_MACHINE_NOINST": "/var/noinstfs/aqua/root.d/registry"
}.toTable

var hiveShortMap = {
  "HKLM": "HKEY_LOCAL_MACHINE",
  "HKCU": "HKEY_CURRENT_USER",
  "HKVM": "HKEY_VOLATILE_MEMORY",
  "HKNS": "HKEY_LOCAL_MACHINE_NOINST"
}.toTable

let priority = @["HKVM", "HKCU", "HKLM", "HKNS"]

let typesAvailable = @["dword", "qword", "bool", "str", "list", "hex", "float", "double"]

# ----------------------------
# Internal helpers
# ----------------------------
proc canonicalHiveName(name: string): string =
  if name.len == 0: return ""
  let n = name.strip()
  if hiveMap.hasKey(n): return n
  if hiveShortMap.hasKey(n): return hiveShortMap[n]
  return ""

proc expandHivePaths(hMap: Table[string, string] = hiveMap): Table[string, string] =
  result = initTable[string, string]()
  for hive, path in hMap.pairs:
    var p = path.replace("$HOME", getHomeDir()[0..^2]) # getHomeDir includes trailing slash
    # Nim's os.expandTilde handles '~'
    p = expandTilde(p)
    result[hive] = absolutePath(p)

proc splitHiveAndRel(registryPath: string): tuple[hive: string, rel: string] =
  var p = registryPath
  if p.startsWith("/"): p = p[1..^1]
  let parts = p.split("/", 1)
  let cand = parts[0]
  let canon = canonicalHiveName(cand)
  if canon.len > 0:
    let rel = if parts.len > 1: parts[1] else: ""
    return (canon, rel)
  return ("", p)

proc valueFileCandidates(baseNoExt: string): seq[string] =
  result = @[]
  for t in typesAvailable:
    result.add(baseNoExt & "." & t & ".rv")

proc detectValueFile(baseNoExt: string): string =
  for f in valueFileCandidates(baseNoExt):
    if fileExists(f):
      return f
  return ""

proc readValueFile(path: string): JsonNode =
  let data = readFile(path).strip()

  if path.endsWith(".dword.rv") or path.endsWith(".qword.rv"):
    return %parseInt(data)
  if path.endsWith(".float.rv") or path.endsWith(".double.rv"):
    return %parseFloat(data)
  if path.endsWith(".hex.rv"):
    return %parseHexInt(data)
  if path.endsWith(".list.rv"):
    let sentinel = $genOid()
    let safeData = data.replace("\\,", sentinel)
    var items: seq[JsonNode] = @[]
    for item in safeData.split(","):
      items.add(%item.strip().replace(sentinel, ","))
    return %items
  if path.endsWith(".bool.rv"):
    let d = data.toLowerAscii()
    return %(d in ["1", "true", "yes", "on"])
  if path.endsWith(".str.rv"):
    return %data
  return %data

proc ensureDir(path: string) =
  createDir(path)

proc priorityHives(): seq[string] =
  result = @[]
  for short in priority:
    var canon = canonicalHiveName(short)
    if canon.len == 0: canon = canonicalHiveName(short.toUpperAscii())
    if canon.len > 0: result.add(canon)

proc encodeKey(keyPart: string): string =
  return encodeUrl(keyPart, usePlus=false)

proc decodeKey(encodedPart: string): string =
  return decodeUrl(encodedPart)

proc getEncodedPath(root: string, relPath: string): string =
  let parts = relPath.split('/')
  var encodedParts: seq[string] = @[]
  for p in parts:
    encodedParts.add(encodeKey(p))
  return root / encodedParts.join(DirSep)

proc execHookSecure(hook: string, newValue: string) =
  try:
    let parts = parseCmdLine(hook)
    var cmdArgs: seq[string] = @[]
    for part in parts:
      cmdArgs.add(part.replace("{}", newValue))

    if cmdArgs.len > 0:
      let exe = cmdArgs[0]
      let args = cmdArgs[1..^1]
      let p = startProcess(exe, args=args, options={poUsePath})
      discard p.waitForExit()
      p.close()
  except CatchableError as e:
    echo "Warning: Failed to execute hook '", hook, "': ", e.msg

# ----------------------------
# Public API
# ----------------------------

# Note: To compile as a Python module, import `nimpy` at the top of the file
# and add `{.exportpy.}` to the `read`, `write`, and `delete` procs.
# You can map `JsonNode` back and forth using python's `json.loads`/`json.dumps`
# or rewrite the interface to accept `PyObject`.

proc readReg*(registryPath: string, defaultVal: JsonNode = newJNull(), hMap: Table[string, string] = hiveMap): JsonNode =
  let expandedMap = expandHivePaths(hMap)
  let (explicitHive, rel) = splitHiveAndRel(registryPath)

  if explicitHive.len > 0:
    let root = expandedMap.getOrDefault(explicitHive, "")
    if root.len == 0: return defaultVal

    let base = getEncodedPath(root, rel)

    if dirExists(base):
      result = newJObject()
      for kind, fpath in walkDir(base):
        let fname = extractFilename(fpath)
        if kind == pcFile and fpath.endsWith(".rv"):
          let parts = fname.rsplit(".", 2)
          if parts.len == 3:
            let name = decodeKey(parts[0])
            result[name] = %parts[1]
        elif kind == pcDir:
          result[fname] = %"key"
      return result

    let cand = detectValueFile(base)
    if cand.len > 0: return readValueFile(cand)
    return defaultVal

  var mergedListing = newJObject()
  var candidates: seq[string] = @[]
  for hive in priorityHives():
    let root = expandedMap.getOrDefault(hive, "")
    if root.len > 0: candidates.add(root / rel)

  var anyDir = false
  for b in candidates:
    if dirExists(b): anyDir = true

  if anyDir:
    for base in candidates:
      if not dirExists(base): continue
      for kind, fpath in walkDir(base):
        let fname = extractFilename(fpath)
        if kind == pcFile and fpath.endsWith(".rv"):
          let parts = fname.rsplit(".", 2)
          if parts.len == 3:
            let name = decodeKey(parts[0])
            if not mergedListing.hasKey(name):
              mergedListing[name] = %parts[1]
        elif kind == pcDir:
          if not mergedListing.hasKey(fname):
            mergedListing[fname] = %"key"
    return mergedListing

  for base in candidates:
    let cand = detectValueFile(base)
    if cand.len > 0: return readValueFile(cand)
  return defaultVal

proc writeReg*(asUser: string, registryPath: string, value: string, typeDef: string = "", isBool: bool = false, isInt: bool = false, isFloat: bool = false, isList: bool = false, hMap: Table[string, string] = hiveMap) =
  let expandedMap = expandHivePaths(hMap)
  let (explicitHive, rel) = splitHiveAndRel(registryPath)

  var targetHive = explicitHive
  if targetHive.len == 0:
    targetHive = canonicalHiveName("HKCU")
    if targetHive.len == 0: raise newException(ValueError, "HKCU is not defined in the hive map.")

  let root = expandedMap.getOrDefault(targetHive, "")
  if root.len == 0: raise newException(ValueError, "Hive '" & targetHive & "' has no valid root path.")

  let baseNoExt = getEncodedPath(root, rel)
  let dirPath = parentDir(baseNoExt)
  ensureDir(dirPath)

  var uid = geteuid()
  var gid = getegid()

  if targetHive == "HKEY_CURRENT_USER":
    let userHome = expandTilde("~" & asUser)
    let pwName = extractFilename(userHome)
    let pwRecord = getpwnam(cstring(pwName))
    if pwRecord != nil:
      uid = pwRecord.pw_uid
      gid = pwRecord.pw_gid

  if targetHive == "HKEY_CURRENT_USER":
    let relDir = dirPath.replace(root, "")
    let dirComponents = relDir.split(DirSep)
    var cumulativePath = root
    for component in dirComponents:
      if component.len > 0:
        cumulativePath = cumulativePath / component
        try: discard chown(cstring(cumulativePath), uid, gid)
        except OSError: discard

  var filePath = ""
  var data = value

  if typeDef.len > 0:
    filePath = baseNoExt & "." & typeDef.toLowerAscii() & ".rv"
  elif isBool:
    filePath = baseNoExt & ".bool.rv"
    data = if value.toLowerAscii() in ["1", "true"]: "1" else: "0"
  elif isInt:
    let valInt = parseInt(value)
    if valInt >= -2147483648 and valInt < 2147483647:
      filePath = baseNoExt & ".dword.rv"
    else:
      filePath = baseNoExt & ".qword.rv"
  elif isFloat:
    let valFloat = parseFloat(value)
    if abs(valFloat) < 3.4e38: filePath = baseNoExt & ".float.rv"
    else: filePath = baseNoExt & ".double.rv"
  elif isList:
    filePath = baseNoExt & ".list.rv"
    # value expected to be pre-formatted comma string in this simplified interface
  else:
    filePath = baseNoExt & ".str.rv"

  let tempFilePath = filePath & ".tmp." & $genOid()
  try:
    var f = open(tempFilePath, fmWrite)
    f.write(data)
    flushFile(f)
    discard fsync(getFileHandle(f))
    f.close()

    if fileExists(filePath):
      setFilePermissions(tempFilePath, getFilePermissions(filePath))

    moveFile(tempFilePath, filePath)
  except CatchableError as e:
    if fileExists(tempFilePath): removeFile(tempFilePath)
    raise e

  if targetHive == "HKEY_CURRENT_USER":
    try: discard chown(cstring(filePath), uid, gid)
    except OSError: discard

  # Hooks
  let keyPathExplicit = rel
  let keyPathImplicit = registryPath
  if keyPathImplicit.startsWith("/"): keyPathImplicit = keyPathImplicit[1..^1]

  let hookPath = "HKEY_LOCAL_MACHINE/SYSTEM/Services/me.hysong.aqua/RegistryPropagator/ActionHooks/"

  let hooksExplicit = readReg(hookPath & "/" & keyPathExplicit, newJNull(), hMap)
  let hooksImplicit = readReg(hookPath & "/" & keyPathImplicit, newJNull(), hMap)

  var hooks: JsonNode
  if hooksExplicit.kind == JArray and hooksExplicit.len > 0:
    hooks = hooksExplicit
  else:
    hooks = hooksImplicit

  if hooks.kind == JArray:
    for execLine in hooks.elems:
      execHookSecure(execLine.getStr().strip(), data)
  elif hooks.kind == JString:
    execHookSecure(hooks.getStr().strip(), data)


proc deleteReg*(registryPath: string, hMap: Table[string, string] = hiveMap): bool =
  let expandedMap = expandHivePaths(hMap)
  let (explicitHive, rel) = splitHiveAndRel(registryPath)

  var targetHive = explicitHive
  if targetHive.len == 0:
    targetHive = canonicalHiveName("HKCU")
    if targetHive.len == 0: return false

  let root = expandedMap.getOrDefault(targetHive, "")
  if root.len == 0: return false

  let target = root / rel

  if dirExists(target):
    removeDir(target)
    return true

  for fpath in valueFileCandidates(target):
    if fileExists(fpath):
      removeFile(fpath)
      return true
  return false

# ----------------------------
# CLI utility
# ----------------------------

when isMainModule:
  if paramCount() < 3:
    echo "Usage: nimreg <user> <action> <registry_path> [type (for write)] [value (for write)]"
    quit(0)

  let user = paramStr(1)
  let action = paramStr(2).toLowerAscii()
  let path = paramStr(3)

  var customHiveMap = hiveMap
  customHiveMap["HKEY_CURRENT_USER"] = expandTilde("~" & user) / defaultLocalPath

  if action == "read":
    var defaultVal = newJNull()
    if paramCount() >= 4: defaultVal = %paramStr(4)
    let result = readReg(path, defaultVal, customHiveMap)
    echo result.pretty()

  elif action == "write":
    if paramCount() < 5:
      echo "Value and type is required for write action."
      quit(0)
    let typedef = paramStr(4)
    let value = paramStr(5)
    writeReg(user, path, value, typeDef=typedef, hMap=customHiveMap)

  elif action == "install":
    if paramCount() < 3:
      echo "File path is required for install action."
      quit(0)
    let filePath = paramStr(3)
    if not fileExists(filePath):
      echo "File '", filePath, "' does not exist."
      quit(0)

    let fileContent = readFile(filePath)

    for rawLine in fileContent.splitLines():
      var line = rawLine.strip()
      if line.len == 0 or line.startsWith("#"): continue

      var skipIfExists = false
      if line.startsWith("?"):
        skipIfExists = true
        line = line[1..^1].strip()

      if "=" in line:
        let parts = line.split("=", 1)
        var keyPath = parts[0].strip()
        let rawValue = parts[1].strip()
        var typedef = ""

        if ":" in keyPath:
          let kParts = keyPath.rsplit(":", 1)
          keyPath = kParts[0].strip()
          typedef = kParts[1].strip()

        if skipIfExists:
          let existing = readReg(keyPath, newJNull(), customHiveMap)
          if existing.kind != JNull:
            echo "Skipping existing key/value '", keyPath, "'"
            continue

        writeReg(user, keyPath, rawValue, typeDef=typedef, hMap=customHiveMap)
        echo "Wrote '", keyPath, "': ", rawValue
      else:
        let keyPath = line
        if skipIfExists:
          let existing = readReg(keyPath, newJNull(), customHiveMap)
          if existing.kind != JNull:
            echo "Skipping existing key '", keyPath, "'"
            continue

        writeReg(user, keyPath / "__dummy__", "", hMap=customHiveMap)
        discard deleteReg(keyPath / "__dummy__", customHiveMap)
        echo "Created key '", keyPath, "'"

  elif action == "delete":
    let ok = deleteReg(path, customHiveMap)
  else:
    echo "Unknown action: ", action
