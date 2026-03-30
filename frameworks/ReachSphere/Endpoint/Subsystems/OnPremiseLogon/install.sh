#!/bin/bash

if [ "$EUID" -ne 0 ]; then
    echo "Please run as root"
    exit
fi

BASE="{{SYS_FRAMEWORKS}}/ReachSphereEndpoint/Subsystems/OnPremiseLogon"
ndauthhook="${BASE}/pam.py"
ndauthhook_authonly="${BASE}/authonly.py"

chmod +x "$ndauthhook" "$ndauthhook_authonly"
chown root:root "$ndauthhook" "$ndauthhook_authonly"

# 전체 로그인 훅 (gdm)
add_hook() {
    local pam_file="$1"
    local hook_script="$2"
    local hook_line="auth required pam_exec.so expose_authtok quiet ${hook_script} --pam=\"${pam_file}\""

    if ! grep -Fxq "$hook_line" "$pam_file"; then
        echo "Adding hook to $pam_file"
        sed -i "1i $hook_line" "$pam_file"
    else
        echo "Hook already present in $pam_file"
    fi
}

add_hook "/etc/pam.d/gdm-password"  "$ndauthhook"          # 로그인 (전체)
add_hook "/etc/pam.d/passwd"        "$ndauthhook_authonly" # 비밀번호 변경
add_hook "/etc/pam.d/sudo"          "$ndauthhook_authonly" # sudo
add_hook "/etc/pam.d/su"            "$ndauthhook_authonly" # su
add_hook "/etc/pam.d/polkit-1"      "$ndauthhook_authonly" # GUI 권한 요청

# OpenSSH 서버가 설치되어 있다면
if [ -f "/etc/pam.d/sshd" ]; then
    add_hook "/etc/pam.d/sshd" "$ndauthhook_authonly" # SSH 로그인
elif [ -f "/etc/pam.d/ssh" ]; then
    add_hook "/etc/pam.d/ssh" "$ndauthhook_authonly" # SSH 로그인
fi
