#!/usr/bin/env python3
import argparse
import sys
import os
import time
import threading
import fnmatch
from wsgidav.wsgidav_app import WsgiDAVApp
from wsgidav.dc.simple_dc import SimpleDomainController
from cheroot import wsgi

def parse_args():
    parser = argparse.ArgumentParser(description="Open a temporary WebDAV server.")

    # Defaults
    default_dir = os.getcwd()
    default_ip = "192.168.*.*,127.0.0.1"

    # Define arguments
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--directory", "-d", default=None, help="Directory to share")
    group.add_argument("--file", "-f", default=None, help="Single file to share")
    parser.add_argument("--capabilities", default="download", help="download,upload")
    parser.add_argument("--accounts", default="user:1111", help="id:pw,id:pw")
    parser.add_argument("--allow-anonymous", default="none", help="download,upload or none")
    parser.add_argument("--autoclose", default="5min", help="Time before auto-shutdown (e.g. 5min)")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on")
    parser.add_argument("--ip", default=default_ip, help="Allowed IPs (comma separated, supports wildcards)")

    # Add the interactive toggle
    parser.add_argument("--interactive", action="store_true", help="Interactively input arguments via stdin")

    args = parser.parse_args()

    # If interactive mode is triggered, prompt for each value
    if args.interactive:
        print("\n--- Interactive Configuration Mode ---")
        print("Press Enter to keep the default value shown in brackets.\n")

        if not args.file:
            path_input = input(f"Directory or File to share [{default_dir}]: ") or default_dir
            if os.path.isfile(path_input):
                 args.file = path_input
                 args.directory = None
            else:
                 args.directory = path_input
                 args.file = None
        else:
             # If file was passed via CLI, we might want to confirm or allow change,
             # but to keep it simple let's stick to the mutually exclusive logic
             pass
        args.capabilities = input(f"Capabilities (download,upload) [{args.capabilities}]: ") or args.capabilities
        args.accounts = input(f"Accounts (id:pw,id:pw) [{args.accounts}]: ") or args.accounts
        args.allow_anonymous = input(f"Allow anonymous (download,upload,none) [{args.allow_anonymous}]: ") or args.allow_anonymous
        args.autoclose = input(f"Autoclose time (e.g. 5min) [{args.autoclose}]: ") or args.autoclose

        # Handle the integer conversion for port
        port_input = input(f"Port [{args.port}]: ")
        if port_input:
            args.port = int(port_input)

        args.ip = input(f"Allowed IPs [{args.ip}]: ") or args.ip
        print("\nConfiguration complete.\n")

    # Post-processing to ensure default directory behavior if nothing specified
    if not args.directory and not args.file:
        args.directory = default_dir

    return args

class SingleFileMiddleware:
    """WSGI Middleware to restrict access to a single file."""
    def __init__(self, app, filename):
        self.app = app
        self.filename = filename.lstrip("/") # Ensure relative for check
        self.allowed_path = f"/{self.filename}"

    def __call__(self, environ, start_response):
        path_info = environ.get("PATH_INFO", "")
        
        # 1. Exact match for the file
        if path_info == self.allowed_path:
             return self.app(environ, start_response)
        
        # 2. Redirect root to the file
        if path_info == "/" or path_info == "":
            start_response("302 Found", [("Location", self.allowed_path)])
            return []

        # 3. Block everything else
        start_response("403 Forbidden", [("Content-Type", "text/plain")])
        return [b"Access denied: Single file sharing mode."]

class IPFilterMiddleware:
    """WSGI Middleware to filter requests based on Allowed IPs."""
    def __init__(self, app, allowed_ips):
        self.app = app
        self.allowed_ips = [ip.strip() for ip in allowed_ips.split(',')]

    def __call__(self, environ, start_response):
        remote_addr = environ.get("REMOTE_ADDR", "")

        # Check if IP matches any pattern
        allowed = False
        for pattern in self.allowed_ips:
            # Simple wildcard translation for standard globbing
            if fnmatch.fnmatch(remote_addr, pattern):
                allowed = True
                break

        if not allowed:
            start_response("403 Forbidden", [("Content-Type", "text/plain")])
            return [f"Access denied for IP: {remote_addr}".encode("utf-8")]

        return self.app(environ, start_response)

def shutdown_server(duration_str):
    """Parses time string and shuts down server after delay."""
    try:
        if "min" in duration_str:
            minutes = int(duration_str.replace("min", ""))
            seconds = minutes * 60
        elif "s" in duration_str:
            seconds = int(duration_str.replace("s", ""))
        else:
            seconds = int(duration_str) # assume seconds if no unit

        print(f"[*] Autoclose timer started: Server will shut down in {duration_str}.")
        time.sleep(seconds)
        print("\n[!] Time limit reached. Shutting down...")
        os._exit(0)
    except ValueError:
        print(f"[!] Invalid autoclose format: {duration_str}. Timer not started.")

def main():
    args = parse_args()

    # 1. Configuration: Path & Mode
    single_file_mode = False
    target_file = None
    
    if args.file:
        if not os.path.exists(args.file):
             print(f"[!] Error: File not found: {args.file}")
             sys.exit(1)
        single_file_mode = True
        args.directory = os.path.dirname(os.path.abspath(args.file))
        target_file = os.path.basename(args.file)
    elif not os.path.isdir(args.directory):
         print(f"[!] Error: Directory not found: {args.directory}")
         sys.exit(1)

    # 1b. Configuration: Capabilities
    # If "upload" is NOT in capabilities, we default to read-only for authenticated users
    # (unless overridden by anonymous settings, but WsgiDAV handles this hierarchically)
    readonly = "upload" not in args.capabilities

    # 2. Configuration: Accounts
    user_mapping = {}
    if args.accounts and args.accounts.lower() != "none":
        for acc in args.accounts.split(','):
            if ':' in acc:
                u, p = acc.split(':', 1)
                user_mapping[u] = {'password': p}

    # 3. Configuration: Anonymous Access
    # In WsgiDAV, True=anonymous allowed, False=required login
    # We map 'allow-anonymous' permissions to simple booleans for the config
    accept_basic = True
    accept_digest = True
    default_to_digest = True

    # If anonymous has upload rights, they get everything.
    # If they have download only, we restrict write.
    # Logic: If allow-anonymous is 'none', we force authentication.
    if args.allow_anonymous.lower() == "none":
        anonymous_allowed = False
    else:
        anonymous_allowed = True
        # If anonymous can ONLY download, we might need to enforce strict read-only at the provider level
        # or rely on WsgiDAV's granular ACLs (which are complex).
        # For this simple script, if anonymous is enabled, we generally allow the capabilities defined globally.

    # 4. WsgiDAV Configuration Dictionary
    # SimpleDomainController requires user_mapping to be keyed by realm (e.g. "*" or "/")
    if anonymous_allowed:
        final_user_mapping = {"*": True}
    else:
        final_user_mapping = {"*": user_mapping}

    config = {
        "host": "0.0.0.0", # We listen on all, but filter via Middleware
        "port": args.port,
        "provider_mapping": {"/": args.directory},
        "simple_dc": {"user_mapping": final_user_mapping},
        "verbose": 1,
        "dir_browser": {"enable": True}, # Fancy HTML directory listing
        "http_authenticator": {
            "domain_controller": SimpleDomainController,
            "accept_basic": accept_basic,
            "accept_digest": accept_digest,
            "default_to_digest": default_to_digest,
        },
    }

    # Apply Read-Only logic based on args
    # Note: WsgiDAV simple config applies readonly to the filesystem provider generally
    if readonly:
        # This forces Read-Only for EVERYONE
        config["provider_mapping"] = {"/": {"root": args.directory, "readonly": True}}

    # 5. Initialize App and Middleware
    app = WsgiDAVApp(config)

    # Wrap with IP Filter
    app_with_filter = IPFilterMiddleware(app, args.ip)
    
    # Wrap with Single File Middleware if needed
    if single_file_mode:
        app_with_filter = SingleFileMiddleware(app_with_filter, target_file)

    # 6. Start Autoclose Timer
    if args.autoclose:
        t = threading.Thread(target=shutdown_server, args=(args.autoclose,))
        t.daemon = True
        t.start()

    # 7. Start Server
    if single_file_mode:
        print(f"[*] Serving Single File: {target_file} (from {args.directory})")
    else:
        print(f"[*] Serving Directory: {args.directory}")
    print(f"[*] Listening on port {args.port}")
    print(f"[*] Allowed IPs: {args.ip}")
    print(f"[*] Users: {list(user_mapping.keys())}")

    try:
        # We use Cheroot as the WSGI server
        server = wsgi.Server(("0.0.0.0", args.port), app_with_filter)
        server.start()
    except KeyboardInterrupt:
        print("\nStopped by user.")

if __name__ == "__main__":
    main()