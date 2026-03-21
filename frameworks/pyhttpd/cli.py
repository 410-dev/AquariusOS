#!/usr/bin/env python3
# {{SYS_FRAMEWORKS}}/pyhttpd/cli.py

import argparse
import grp
import json
import os
import pwd
import re
import shutil
import socket
import sys

# ── 상수 ─────────────────────────────────────────────────────────

SOCKET_PATH    = "/run/pyhttpd/pyhttpd.sock"
INSTANCES_DIR  = "/etc/pyhttpd/instances"
ENABLED_DIR    = "/etc/pyhttpd/enabled"
INST_PATTERN   = re.compile(r"^(?P<user>[^.]+)\.(?P<context>[^.]+)\.(?P<port>\d+)\.inst$")


# ── IPC 클라이언트 ────────────────────────────────────────────────

def _ipc(cmd: dict, timeout: float = 5.0) -> dict:
    """
    데몬에 JSON 명령을 보내고 응답을 받습니다.
    데몬이 없거나 소켓 연결 실패 시 예외 대신 {"ok": False, "error": ...} 반환.
    """
    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect(SOCKET_PATH)
        sock.sendall(json.dumps(cmd).encode())
        sock.shutdown(socket.SHUT_WR)
        data = b""
        while chunk := sock.recv(4096):
            data += chunk
        sock.close()
        return json.loads(data.decode())
    except FileNotFoundError:
        return {"ok": False, "error": "Daemon is not running (socket not found)"}
    except ConnectionRefusedError:
        return {"ok": False, "error": "Daemon is not running (connection refused)"}
    except TimeoutError:
        return {"ok": False, "error": "Daemon did not respond (timeout)"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _require_daemon():
    """데몬이 없으면 에러 메시지 출력 후 종료."""
    resp = _ipc({"cmd": "ping"})
    if not resp.get("ok"):
        _die(f"Cannot reach pyhttpd daemon: {resp.get('error')}")


# ── 유틸리티 ─────────────────────────────────────────────────────

def _die(msg: str, code: int = 1):
    print(f"Error: {msg}", file=sys.stderr)
    sys.exit(code)


def _ok(msg: str):
    print(msg)


def _current_user() -> str:
    return pwd.getpwuid(os.getuid()).pw_name


def _inst_filename(user: str, context: str, port: int) -> str:
    return f"{user}.{context}.{port}.inst"


def _script_dest(user: str, context: str, port: int) -> str:
    return os.path.join(INSTANCES_DIR, user, f"{context}.{port}.py")


def _ensure_dirs(user: str):
    user_dir = os.path.join(INSTANCES_DIR, user)
    os.makedirs(user_dir,   mode=0o755, exist_ok=True)
    os.makedirs(ENABLED_DIR, mode=0o755, exist_ok=True)


def _validate_context(context: str):
    if not re.match(r'^[a-zA-Z0-9_-]+$', context):
        _die(f"Invalid context name '{context}'. Use only letters, numbers, hyphens, underscores.")


def _validate_script(path: str):
    """
    스크립트가 WebhookTask 서브클래스를 포함하는지 사전 검증.
    cli.py는 apprun venv 밖이므로 import 대신 간이 텍스트 검사.
    확실한 검증은 데몬의 loader가 수행합니다.
    """
    if not os.path.isfile(path):
        _die(f"File not found: {path}")
    if not path.endswith(".py"):
        _die(f"Not a Python file: {path}")
    with open(path) as f:
        source = f.read()
    if "WebhookTask" not in source:
        _die("Script does not appear to contain a WebhookTask subclass.")


# ── 서브커맨드 구현 ───────────────────────────────────────────────

def cmd_register(args):
    user    = _current_user()
    context = args.context
    port    = args.port
    src     = os.path.abspath(args.script)

    _validate_context(context)
    _validate_script(src)
    _ensure_dirs(user)

    dest     = _script_dest(user, context, port)
    inst_name = _inst_filename(user, context, port)
    link_path = os.path.join(ENABLED_DIR, inst_name)

    print(f"Validating... OK")

    # 스크립트 복사
    shutil.copy2(src, dest)
    os.chmod(dest, 0o644)
    print(f"Copied script from {src}")
    print(f"          to {dest}")

    # --enable-now: 심볼릭 링크 생성
    if args.enable_now:
        if os.path.islink(link_path):
            os.unlink(link_path)
        os.symlink(dest, link_path)
        print(f"Created symbolic link {link_path}")
        print(f"                   -> {dest}")

        # 데몬에 reload 요청
        resp = _ipc({"cmd": "reload"})
        if resp.get("ok"):
            print("Registered to pyhttpd.")
            print("Updating routers...")
            print("Success.")
        else:
            # 데몬 없어도 파일은 등록됐으니 경고만
            print(f"Warning: {resp.get('error')}")
            print("Files registered. Start pyhttpd daemon to activate.")
    else:
        print(f"Registered (not enabled). Run: pyhttpd enable {context} --port {port}")


def cmd_unregister(args):
    user     = _current_user()
    context  = args.context
    port     = args.port
    dest     = _script_dest(user, context, port)
    inst_name = _inst_filename(user, context, port)
    link_path = os.path.join(ENABLED_DIR, inst_name)

    # 활성화된 경우 먼저 비활성화
    if os.path.islink(link_path):
        os.unlink(link_path)
        print(f"Disabled: {inst_name}")
        resp = _ipc({"cmd": "reload"})
        if not resp.get("ok"):
            print(f"Warning: {resp.get('error')}")

    if os.path.isfile(dest):
        os.remove(dest)
        print(f"Removed: {dest}")
    else:
        _die(f"Instance not found: {context}:{port}")

    print("Unregistered.")


def cmd_enable(args):
    user      = _current_user()
    context   = args.context
    port      = args.port
    dest      = _script_dest(user, context, port)
    inst_name = _inst_filename(user, context, port)
    link_path = os.path.join(ENABLED_DIR, inst_name)

    if not os.path.isfile(dest):
        _die(f"Instance not registered: {context}:{port}. Run 'pyhttpd register' first.")

    if os.path.islink(link_path):
        _die(f"Already enabled: {context}:{port}")

    _ensure_dirs(user)
    os.symlink(dest, link_path)
    print(f"Enabled: {inst_name}")

    resp = _ipc({"cmd": "reload"})
    if resp.get("ok"):
        print("Success.")
    else:
        print(f"Warning: {resp.get('error')}")


def cmd_disable(args):
    user      = _current_user()
    context   = args.context
    port      = args.port
    inst_name = _inst_filename(user, context, port)
    link_path = os.path.join(ENABLED_DIR, inst_name)

    if not os.path.islink(link_path):
        _die(f"Not enabled: {context}:{port}")

    os.unlink(link_path)
    print(f"Disabled: {inst_name}")

    resp = _ipc({"cmd": "reload"})
    if resp.get("ok"):
        print("Success.")
    else:
        print(f"Warning: {resp.get('error')}")


def cmd_list(args):
    user = _current_user()
    user_dir = os.path.join(INSTANCES_DIR, user)

    if not os.path.isdir(user_dir):
        print("No instances registered.")
        return

    instances = []
    for fname in sorted(os.listdir(user_dir)):
        if not fname.endswith(".py"):
            continue
        # context.port.py
        parts = fname[:-3].rsplit(".", 1)
        if len(parts) != 2:
            continue
        context, port_str = parts
        port = int(port_str)
        inst_name = _inst_filename(user, context, port)
        link_path = os.path.join(ENABLED_DIR, inst_name)
        enabled = os.path.islink(link_path) and os.path.exists(link_path)
        instances.append((context, port, enabled))

    if not instances:
        print("No instances registered.")
        return

    col = "{:<24} {:>6}  {}"
    print(col.format("context", "port", "status"))
    print("-" * 42)
    for context, port, enabled in instances:
        status = "enabled" if enabled else "disabled"
        print(col.format(context, port, status))


def cmd_status(args):
    resp = _ipc({"cmd": "status"})
    if not resp.get("ok"):
        _die(resp.get("error", "Unknown error"))

    ports = resp.get("ports", {})
    if not ports:
        print("No active instances.")
        return

    print("Active instances:")
    print()
    for port, contexts in sorted(ports.items(), key=lambda x: int(x[0])):
        for ctx in sorted(contexts):
            path = "/" if ctx == "root" else f"/{ctx}"
            print(f"  http://localhost:{port}{path}")
    print()


def cmd_reload(args):
    resp = _ipc({"cmd": "reload"})
    if resp.get("ok"):
        print("Reloaded.")
    else:
        _die(resp.get("error", "Unknown error"))


# ── argparse 설정 ─────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pyhttpd",
        description="pyhttpd — Python HTTP webhook daemon manager",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # register
    p_reg = sub.add_parser("register", help="Register a webhook script")
    p_reg.add_argument("script", help="Path to the .py script")
    p_reg.add_argument("--port", type=int, required=True)
    p_reg.add_argument("--context", required=True,
                       help="URL context (use 'root' for /)")
    p_reg.add_argument("--enable-now", action="store_true",
                       help="Also enable and reload immediately")
    p_reg.set_defaults(func=cmd_register)

    # unregister
    p_unreg = sub.add_parser("unregister", help="Unregister a webhook instance")
    p_unreg.add_argument("context")
    p_unreg.add_argument("--port", type=int, required=True)
    p_unreg.set_defaults(func=cmd_unregister)

    # enable
    p_en = sub.add_parser("enable", help="Enable a registered instance")
    p_en.add_argument("context")
    p_en.add_argument("--port", type=int, required=True)
    p_en.set_defaults(func=cmd_enable)

    # disable
    p_dis = sub.add_parser("disable", help="Disable an instance (keep registered)")
    p_dis.add_argument("context")
    p_dis.add_argument("--port", type=int, required=True)
    p_dis.set_defaults(func=cmd_disable)

    # list
    p_list = sub.add_parser("list", help="List registered instances")
    p_list.set_defaults(func=cmd_list)

    # status
    p_stat = sub.add_parser("status", help="Show active instances from daemon")
    p_stat.set_defaults(func=cmd_status)

    # reload
    p_rel = sub.add_parser("reload", help="Force daemon to rescan enabled dir")
    p_rel.set_defaults(func=cmd_reload)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
