#!/usr/bin/env python3
# This is objective shell compatible command.

import sys
import json
import sqlite3
import os
import sys
from datetime import datetime, timezone

sys.path.append("{{SYS_FRAMEWORKS}}/GroupPolicy/Resources/Libraries")
import getpolvalcommon

# Usage:
# Get-PolicyValue <user> <Policy key name>
# Get-PolicyValue john MachineOverride/Timezone

# Returns
# {
#     "Id": "MachineOverride/Timezone"
#     "User": "john"
#     "Name": "시간대",
#     "Description": "장치의 로컬 시간대를 설정합니다."
#     "Type": "string",
#     "Value": "UTC+9",
#     "AppliedBy": {
#         "Name": "Policy ABC",
#         "Id":   "policy-abc",
#         "Time": "2024-01-01T00:00:00Z",
#         "PolicyFileDigest": "sha256:9q4h98dosdikjfasdf984ijasdf",
#         "ByUser": "agent",
#         ..other elements...
#     }
# }

# Note: Localization is in "{{SYS_FRAMEWORKS}}/Localization/Policies/<locale>-title.json" and "{{SYS_FRAMEWORKS}}/Localization/Policies/<locale>-description.json"
# Note: Localization setting cascades to: Machine/LanguageAndRegion/PreferredLocale or <user>/LanguageAndRegion/PreferredLocale
# Note: Policy reader is not implemented yet - leave get_locale as-is for now

# 정책 키에서 테이블명과 polkey 를 분리
# "Machine/Hostname"         → ("Machine", "Hostname")
# "MachineOverride/Timezone" → ("MachineOverride", "Timezone")
# "<username>/SomeKey"       → ("<username>", "SomeKey")



def main(session, username: str, policies_to_read: list[str]) -> tuple[int, list[dict] | str]:
    return getpolvalcommon.fetch_policy_data(username, policies_to_read)


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Usage: Get-PolicyValue <user> <PolicyKey> [PolicyKey2 ...]", file=sys.stderr)
        sys.exit(1)

    exit_code, output = main(None, sys.argv[1], sys.argv[2:])

    if exit_code != 0:
        print(f"Failed to load policy value: {output}", file=sys.stderr)
    else:
        print(json.dumps(output, indent=4, ensure_ascii=False))

    sys.exit(exit_code)
