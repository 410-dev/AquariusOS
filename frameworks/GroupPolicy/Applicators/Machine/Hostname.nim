import os, strutils, dynlib
import std/strformat
import std/json

proc printHelp() =
    echo """
Machine/Hostname <IPC Decryption Key>
"""

const
  AES_256_GCM = 1

type
  AesProc = proc(algo: cint, content: cstring, key: cstring): cstring {.cdecl.}

proc geteuid(): int {.importc, header: "<unistd.h>".}

proc main() =

    if geteuid() != 0:
        echo "Error: Policy control requires root privilege"
        quit(1)

    if paramCount() != 1:
        printHelp()
        quit(1)

    # 예약된 데이터 불러오기
    # 예약 위치: {{AQUA_VFS_ROOT}}/gpofwk/call/machine_hostname.txt
    const reservedLocation = "{{AQUA_VFS_ROOT}}/gpofwk/call/machine_hostname.txt"
    if not fileExists(reservedLocation):
        echo "Error: Call data is not preset in reserved location"
        quit(1)

    # 데이터 읽어들이기
    let contentRaw = readFile(reservedLocation)
    let key = paramStr(1)

    # 데이터 복호화 
    let lib = loadLib("{{SYS_NIMLIBS}}/crypto.so")
    if lib == nil:
        echo "Failed loading crypto.so library. Expected in {{SYS_NIMLIBS}}/crypto.so."
        quit(1)

    let decryptFn = cast[AesProc](lib.symAddr("decrypt_aes"))
    let content = $decryptFn(AES_256_GCM, cstring(contentRaw), cstring(key))
    lib.unloadLib()

    # 데이터 체크
    if content.startsWith("ERROR:"):
        echo &"Failed: {content}"
        quit(1)

    if not content.startsWith("{"):
        echo &"Parsed content is not a valid data format."
        quit(1)

    # JSON 파싱
    let jsonParsed = parseJson(content)
    let value = jsonParsed["value"].getStr()
    
    

if isMainModule:
    main()
