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
import errno
import select
import signal as _signal

CERTS_DIR = "/etc/pyhttpd/certs"

LOG_BASE = "/var/log/pyhttpd"

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

def _inst_filename(user, context, port, proto="http"):
    return f"{user}.{context}.{port}.{proto}.inst"

def _script_dest(user, context, port, proto="http"):
    return os.path.join(INSTANCES_DIR, user, f"{context}.{port}.{proto}.py")

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

    # 프로토콜 결정
    if args.redirect_https:
        proto = "redirect"
    elif args.ssl:
        proto = "https"
    else:
        proto = "http"

    _validate_context(context)
    if proto != "redirect":
        _validate_script(src)
    _ensure_dirs(user)

    dest      = _script_dest(user, context, port, proto)
    inst_name = _inst_filename(user, context, port, proto)
    link_path = os.path.join(ENABLED_DIR, inst_name)

    print("Validating... OK")

    # 인증서 처리 (HTTPS 수동)
    if proto == "https" and not args.acme_domain:
        if not args.ssl_cert or not args.ssl_key:
            _die("--ssl requires --ssl-cert and --ssl-key (or --acme-domain)")
        sys.path.insert(0, "{{SYS_FRAMEWORKS}}/pyhttpd/pyhttpd.apprun")
        from ssl_manager import install_cert
        install_cert(user, context, port, args.ssl_cert, args.ssl_key)
        print(f"Installed certificate for {context}:{port}")

    # 인증서 처리 (ACME)
    if proto == "https" and args.acme_domain:
        import asyncio
        sys.path.insert(0, "{{SYS_FRAMEWORKS}}/pyhttpd/pyhttpd.apprun")
        from ssl_manager import provision_acme
        try:
            asyncio.run(provision_acme(user, context, port, args.acme_domain))
            print(f"ACME certificate issued for {args.acme_domain}")
        except RuntimeError as e:
            _die(str(e))

    # 스크립트 복사 (redirect는 스크립트 불필요)
    if proto != "redirect":
        shutil.copy2(src, dest)
        os.chmod(dest, 0o644)
        print(f"Copied script from {src} to {dest}")

    if args.enable_now:
        if os.path.islink(link_path):
            os.unlink(link_path)
        target = dest if proto != "redirect" else "/dev/null"
        os.symlink(target, link_path)
        print(f"Created symbolic link {link_path}")

        resp = _ipc({"cmd": "reload"})
        if resp.get("ok"):
            print("Registered to pyhttpd.")
            print("Updating routers...")
            print("Success.")
        else:
            print(f"Warning: {resp.get('error')}")
            print("Files registered. Start pyhttpd daemon to activate.")
    else:
        print(f"Registered (not enabled). Run: pyhttpd enable {context} --port {port} --proto {proto}")


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
        # <context>.<port>.<proto>.py
        parts = fname[:-3].rsplit(".", 2)
        if len(parts) != 3:
            continue
        context, port_str, proto = parts
        if not port_str.isdigit():
            continue
        if proto not in ("http", "https", "redirect"):
            continue
        port = int(port_str)
        inst_name = _inst_filename(user, context, port, proto)
        link_path = os.path.join(ENABLED_DIR, inst_name)
        enabled = os.path.islink(link_path) and os.path.exists(link_path)
        instances.append((context, port, proto, enabled))

    if not instances:
        print("No instances registered.")
        return

    col = "{:<24} {:>6}  {:<10}  {}"
    print(col.format("context", "port", "proto", "status"))
    print("-" * 50)
    for context, port, proto, enabled in instances:
        status = "enabled" if enabled else "disabled"
        print(col.format(context, port, proto, status))


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
    p_reg.add_argument("script", nargs="?",
                       help="Path to the .py script (not required for --redirect-https)")
    p_reg.add_argument("--port", type=int, required=True)
    p_reg.add_argument("--context", required=True)
    p_reg.add_argument("--enable-now", action="store_true")
    p_reg.add_argument("--ssl", action="store_true",
                       help="Enable HTTPS for this instance")
    p_reg.add_argument("--ssl-cert", metavar="PATH",
                       help="Path to PEM certificate file")
    p_reg.add_argument("--ssl-key", metavar="PATH",
                       help="Path to PEM private key file")
    p_reg.add_argument("--acme-domain", metavar="DOMAIN",
                       help="Issue certificate via Let's Encrypt for this domain")
    p_reg.add_argument("--redirect-https", action="store_true",
                       help="Register this port as HTTP→HTTPS redirect (no script needed)")
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

    # logs
    p_logs = sub.add_parser("logs", help="View request logs for an instance")
    p_logs.add_argument("context")
    p_logs.add_argument("--port", type=int, required=True)
    p_logs.add_argument("--lines", type=int, metavar="N",
                        help="Show last N lines (default: 20)")
    p_logs.add_argument("--follow", "-f", action="store_true",
                        help="Stream new log entries in real time")
    p_logs.set_defaults(func=cmd_logs)



    return parser



def _log_path(user: str, context: str, port: int) -> str:
    return os.path.join(LOG_BASE, user, f"{context}.{port}.log")


def _format_entry(line: str) -> str:
    try:
        e = json.loads(line)
        status = e.get("status", "?")

        if status >= 500:
            prefix = "ERR"
        elif status >= 400:
            prefix = "WRN"
        else:
            prefix = " OK"

        base = (
            f"[{e.get('ts','?')}] {prefix} "
            f"{e.get('method','?')} {e.get('path','?')} "
            f"→ {status} ({e.get('ms','?')}ms)"
        )

        body = e.get("body", "")
        if body:
            base += f"\n    body: {body.replace(chr(10), ' ')[:120]}"

        # stdout 출력 (print() 캡처 결과)
        stdout_lines = e.get("stdout")
        if stdout_lines:
            formatted = "\n    ".join(stdout_lines)
            base += f"\n    stdout:\n    {formatted}"

        error = e.get("error")
        if error:
            indented = "\n    ".join(error.strip().splitlines())
            base += f"\n    traceback:\n    {indented}"

        return base
    except (json.JSONDecodeError, KeyError):
        return line.rstrip()


def cmd_logs(args):
    user    = _current_user()
    context = args.context
    port    = args.port
    lines   = args.lines
    follow  = args.follow

    log_path = _log_path(user, context, port)

    if not os.path.isfile(log_path):
        _die(f"No log file found: {log_path}\nIs '{context}:{port}' registered?")

    if follow and not lines:
        # --follow 단독: 기존 내용은 건너뛰고 새 줄만 스트리밍
        _tail_follow(log_path, tail_n=0)
    elif follow and lines:
        # --follow --lines N: 마지막 N줄 출력 후 스트리밍
        _tail_follow(log_path, tail_n=lines)
    else:
        # --lines N: 마지막 N줄 출력 후 종료
        _tail_n(log_path, lines or 20)


def _tail_n(path: str, n: int):
    """파일 끝에서 n줄을 읽어 출력합니다."""
    with open(path, "rb") as f:
        # 파일 끝에서 역방향으로 n개 줄바꿈을 찾습니다
        f.seek(0, 2)
        size = f.tell()
        buf = b""
        pos = size
        found = 0

        while pos > 0 and found <= n:
            chunk = min(4096, pos)
            pos -= chunk
            f.seek(pos)
            buf = f.read(chunk) + buf
            found = buf.count(b"\n")

        lines = buf.decode(errors="replace").splitlines()
        for line in lines[-n:]:
            if line.strip():
                print(_format_entry(line))


def _tail_follow(path: str, tail_n: int):
    """tail -f 스타일로 파일을 실시간으로 스트리밍합니다."""
    if tail_n > 0:
        _tail_n(path, tail_n)

    # SIGINT(Ctrl+C) 로 종료
    interrupted = False
    def _on_sigint(sig, frame):
        nonlocal interrupted
        interrupted = True
    _signal.signal(_signal.SIGINT, _on_sigint)

    with open(path, "r", errors="replace") as f:
        f.seek(0, 2)  # 파일 끝으로 이동
        print(f"Following {path} — Ctrl+C to stop")
        while not interrupted:
            line = f.readline()
            if line:
                if line.strip():
                    print(_format_entry(line), flush=True)
            else:
                # 새 줄 없으면 잠시 대기
                select.select([f], [], [], 0.5)


def main():
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
