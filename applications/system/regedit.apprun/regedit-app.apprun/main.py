#!/usr/bin/env python3
import argparse
import json
import os
import re
import shutil
import sys
import subprocess
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from typing import Dict, List, Any

APP_TITLE = "AquariusOS Registry Editor"
VALUE_EXT = ".rv"
VALID_TYPES = ["dword", "qword", "bool", "str", "list", "hex", "float", "double"]

# --- Hive Configuration Constants ---
DEFAULT_HIVES = {
    "HKEY_LOCAL_MACHINE": Path("/opt/aqua/registry"),
    "HKEY_CURRENT_USER": Path(os.path.expanduser("~/.local/aqua/registry")),
    "HKEY_VOLATILE_MEMORY": Path("/opt/aqua/vfs/registry"),
}

HIVE_SHORT_MAP: Dict[str, str] = {
    "HKLM": "HKEY_LOCAL_MACHINE",
    "HKCU": "HKEY_CURRENT_USER",
    "HKVM": "HKEY_VOLATILE_MEMORY",
}
# --- End Hive Configuration ---

TYPE_LABELS = {
    "str":   "Text",
    "dword": "DWORD (32 bit Integer)",
    "qword": "QWORD (64 bit Integer)",
    "list":  "List",
    "bool":  "Boolean",
    "hex":   "Hexadecimal",
    "float": "Decimal (32 bit)",
    "double":"Decimal (64 bit)",
}
LABEL_TO_TYPE = {v: k for k, v in TYPE_LABELS.items()}

ICON_SIZE = 12  # px
PREVIEW_MAX = 40  # ~40 characters in preview column

def parse_value_filename(filename: str):
    """
    <value name>.<type>.rv  -> returns (name, type) or (None, None) if not valid.
    """
    if not filename.endswith(VALUE_EXT):
        return None, None
    stem = filename[:-len(VALUE_EXT)]
    if "." not in stem:
        return None, None
    name, vtype = stem.rsplit(".", 1)
    if vtype not in VALID_TYPES or not name:
        return None, None
    return name, vtype

# --- Privilege Management ---

class PrivilegedExecutor:
    """Manages a persistent, elevated helper process for filesystem operations."""
    def __init__(self, parent_widget):
        self.parent = parent_widget
        self.helper_process = None
        self._launch_helper()

    def _launch_helper(self):
        helper_script = Path(__file__).parent / "privileged_helper.py"
        if not helper_script.exists():
            messagebox.showerror("Error", f"Helper script not found:\n{helper_script}")
            return

        try:
            self.helper_process = subprocess.Popen(
                ['pkexec', sys.executable, str(helper_script)],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                text=True,
                bufsize=1 # Line-buffered
            )
        except Exception as e:
            messagebox.showerror("Privilege Escalation Failed", f"Could not start the privileged helper process.\n\nError: {e}")
            self.helper_process = None

    def _execute(self, command: Dict[str, Any]) -> Dict[str, Any] | None:
        if not self.helper_process or self.helper_process.poll() is not None:
            messagebox.showwarning("Privilege Lost", "The privileged helper process is not running. Please restart the application.")
            return None

        try:
            self.helper_process.stdin.write(json.dumps(command) + '\n')
            self.helper_process.stdin.flush()
            response_line = self.helper_process.stdout.readline()
            return json.loads(response_line)
        except (BrokenPipeError, OSError, json.JSONDecodeError) as e:
            messagebox.showerror("Communication Error", f"Lost connection to the privileged helper.\n\nError: {e}")
            self.close()
            return None

    def close(self):
        if self.helper_process and self.helper_process.poll() is None:
            try:
                self.helper_process.stdin.write(json.dumps({"action": "exit"}) + '\n')
                self.helper_process.stdin.flush()
                self.helper_process.terminate()
            except (IOError, OSError):
                pass # Ignore errors on close
        self.helper_process = None

    def _run_action(self, action: str, **kwargs) -> bool:
        command = {"action": action, **kwargs}
        response = self._execute(command)
        if response and response.get("status") == "ok":
            return True
        elif response:
            msg = response.get("message", "An unknown error occurred.")
            messagebox.showerror("Privileged Action Failed", msg)
        return False

    def mkdir(self, path: Path) -> bool: return self._run_action("mkdir", path=str(path))
    def rmtree(self, path: Path) -> bool: return self._run_action("rmtree", path=str(path))
    def rename(self, src: Path, dst: Path) -> bool: return self._run_action("rename", src=str(src), dst=str(dst))
    def unlink(self, path: Path) -> bool: return self._run_action("unlink", path=str(path))
    def write_text(self, path: Path, content: str) -> bool: return self._run_action("write_text", path=str(path), content=content)

class DirectExecutor:
    """A non-privileged executor that calls pathlib and shutil directly."""
    def mkdir(self, path: Path) -> bool: path.mkdir(parents=False, exist_ok=False); return True
    def rmtree(self, path: Path) -> bool: shutil.rmtree(path); return True
    def rename(self, src: Path, dst: Path) -> bool: src.rename(dst); return True
    def unlink(self, path: Path) -> bool: path.unlink(missing_ok=True); return True
    def write_text(self, path: Path, content: str) -> bool: path.write_text(content, encoding="utf-8"); return True
    def close(self): pass # No-op for direct executor

# --- End Privilege Management ---

def serialize_value(value_str: str, vtype: str):
    if vtype == "list":
        # New format: split by comma, wrap each item in quotes, join with ', '
        items = value_str.split(',')
        return ",".join(items)
    if vtype == "str": return value_str
    if vtype == "bool":
        val = value_str.strip()
        if val in {"0", "1"}: return val
        raise ValueError("Boolean must be 0 or 1.")
    if vtype in ("dword", "qword"):
        try: n = int(value_str, 0)
        except Exception: raise ValueError(f"{vtype.upper()} must be an integer.")
        if vtype == "dword" and not (-0x80000000 <= n <= 0x7FFFFFFF):
            raise ValueError("DWORD must be a signed 32-bit integer.")
        if vtype == "qword" and not (-0x8000000000000000 <= n <= 0x7FFFFFFFFFFFFFFF):
            raise ValueError("QWORD must be a signed 64-bit integer.")
        return str(n)
    if vtype in ("float", "double"):
        try: f = float(value_str)
        except Exception: raise ValueError(f"{vtype.title()} must be a number.")
        return str(f)
    if vtype == "hex":
        s = value_str.strip().lower().removeprefix("0x")
        if not s: return ""
        if not re.fullmatch(r"[0-9a-f]+", s): raise ValueError("HEX must contain only 0-9 and a-f.")
        if len(s) % 2 != 0: raise ValueError("HEX must have an even number of digits.")
        return s
    raise ValueError(f"Unsupported type: {vtype}")

def deserialize_value(content: str, vtype: str) -> str:
    # if vtype == "list":
    #     # New format: find all quoted strings, join them with a comma for the editor
    #     items = re.findall(r"'([^']*)'", content)
    #     return ",".join(items)
    return content

def preview_for(vtype: str, raw_text: str) -> str:
    s = raw_text or ""
    try:
        if vtype == "list": return ellipsize(s) # The new format is already readable
        if vtype == "bool": return "True" if s.strip() == "1" else "False"
        if vtype == "dword": return str(to_signed(int(s, 0) if s.strip().startswith(("0x", "0X")) else int(s or "0"), 32))
        if vtype == "qword": return str(to_signed(int(s, 0) if s.strip().startswith(("0x", "0X")) else int(s or "0"), 64))
        if vtype == "hex": return ellipsize("0x" + s.strip().lower() if s.strip() else "")
        if vtype in ("float", "double"): return ellipsize(str(float(s)))
        return ellipsize(s)
    except Exception: return "(invalid)"

def to_signed(n: int, bits: int) -> int:
    sign_bit = 1 << (bits - 1)
    return (n & ((1 << bits) - 1)) - (1 << bits) if (n & sign_bit) else n

def ellipsize(s: str, limit: int = PREVIEW_MAX) -> str:
    return s if len(s or "") <= limit else (s[:limit] + "...")

class Icons:
    def __init__(self, root):
        self.folder = self._draw_folder_icon(root)
        self.type_icons = {t: self._color_square(root, c) for t, c in {
            "dword": "blue", "qword": "red", "bool": "black",
            "str": "purple", "list": "cyan", "hex": "magenta"}.items()}
    def _color_square(self, root, color: str):
        img = tk.PhotoImage(width=ICON_SIZE, height=ICON_SIZE, master=root)
        img.put(color, to=(0, 0, ICON_SIZE, ICON_SIZE)); return img
    def _draw_folder_icon(self, root):
        w = h = ICON_SIZE + 4
        img = tk.PhotoImage(width=w, height=h, master=root)
        img.put("goldenrod", to=(1, 5, w - 2, h - 2))
        img.put("khaki", to=(1, 1, int(w*0.55), 6)); return img

class ValueEditorDialog(tk.Toplevel):
    def __init__(self, parent, title, initial_name="", initial_type="str", initial_value=""):
        super().__init__(parent)
        self.transient(parent); self.title(title); self.resizable(False, False)
        self.result = None
        frm = ttk.Frame(self, padding=10); frm.grid(sticky="nsew")
        ttk.Label(frm, text="Name:").grid(row=0, column=0, sticky="w", padx=(0,6), pady=4)
        self.name_var = tk.StringVar(value=initial_name)
        ent_name = ttk.Entry(frm, textvariable=self.name_var, width=40)
        ent_name.grid(row=0, column=1, sticky="ew", pady=4)
        ttk.Label(frm, text="Type:").grid(row=1, column=0, sticky="w", padx=(0,6), pady=4)
        allowed_labels = list(TYPE_LABELS.values())
        self.type_label_var = tk.StringVar(value=TYPE_LABELS.get(initial_type, allowed_labels[0]))
        cb_type = ttk.Combobox(frm, textvariable=self.type_label_var, values=allowed_labels, state="readonly", width=28)
        cb_type.grid(row=1, column=1, sticky="w", pady=4)
        ttk.Label(frm, text="Value:").grid(row=2, column=0, sticky="nw", padx=(0,6), pady=4)
        self.value_txt = tk.Text(frm, width=40, height=6)
        self.value_txt.grid(row=2, column=1, sticky="ew", pady=4)
        self.value_txt.insert("1.0", initial_value if isinstance(initial_value, str) else "")
        btns = ttk.Frame(frm); btns.grid(row=3, column=0, columnspan=2, sticky="e", pady=(8,0))
        ttk.Button(btns, text="Save", command=self._on_ok).grid(row=0, column=0, padx=4)
        ttk.Button(btns, text="Cancel", command=self._on_cancel).grid(row=0, column=1, padx=4)
        self.bind("<Return>", lambda e: self._on_ok()); self.bind("<Escape>", lambda e: self._on_cancel())
        self.wait_visibility(); self.grab_set(); ent_name.focus_set(); self.wait_window(self)
    def _on_ok(self):
        name = self.name_var.get().strip()
        vtype = LABEL_TO_TYPE.get(self.type_label_var.get(), "str")
        value = self.value_txt.get("1.0", "end").strip()
        if not name: messagebox.showerror("Error", "Name cannot be empty.", parent=self); return
        try: normalized = serialize_value(value, vtype)
        except ValueError as e: messagebox.showerror("Validation Error", str(e), parent=self); return
        self.result = (name, vtype, normalized); self.destroy()
    def _on_cancel(self): self.result = None; self.destroy()

class RegistryEditor(tk.Tk):
    def __init__(self, hives: Dict[str, Path], is_root: bool):
        super().__init__()
        self.title(APP_TITLE); self.geometry("1100x640"); self.minsize(900, 540)
        self.hives = hives
        self.is_root = is_root
        self.icons = Icons(self)

        if self.is_root:
            self.executor = DirectExecutor()
        else:
            self.executor = PrivilegedExecutor(self)

        self.direct_executor = DirectExecutor() # Still need this for HKCU
        self.privileged_hives = {
            h_name for h_name in [HIVE_SHORT_MAP.get("HKLM"), HIVE_SHORT_MAP.get("HKVM")] if h_name
        }
        self._build_ui(); self._wire_events(); self.refresh_tree()
        self.protocol("WM_DELETE_WINDOW", self._on_closing)

    def _on_closing(self):
        """Ensure the helper process is terminated before exiting."""
        self.executor.close()
        self.destroy()

    def _get_executor(self, path: Path):
        """Get the correct executor based on the path."""
        if self.is_root or not self._is_privileged_path(path):
            return self.direct_executor
        return self.executor

    def _build_ui(self):
        menubar = tk.Menu(self)
        edit_menu = tk.Menu(menubar, tearoff=False)
        edit_menu.add_command(label="New Key", command=self.action_new_key)
        edit_menu.add_command(label="New Value", command=self.action_new_value)
        edit_menu.add_separator()
        edit_menu.add_command(label="Rename...", command=self.action_rename)
        edit_menu.add_command(label="Delete", command=self.action_delete)
        menubar.add_cascade(label="Edit", menu=edit_menu)
        ext_menu = tk.Menu(menubar, tearoff=False)
        ext_menu.add_command(label="Export", command=self.action_export)
        ext_menu.add_command(label="Import", command=self.action_import)
        ext_menu.add_command(label="Merge", command=self.action_merge)
        menubar.add_cascade(label="External", menu=ext_menu)
        self.config(menu=menubar)
        self.paned = ttk.Panedwindow(self, orient="horizontal"); self.paned.pack(fill="both", expand=True)
        lf = ttk.Frame(self.paned); self.paned.add(lf, weight=1)
        self.tree = ttk.Treeview(lf, columns=("path",), displaycolumns=(), show="tree")
        vsb = ttk.Scrollbar(lf, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(lf, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew"); vsb.grid(row=0, column=1, sticky="ns"); hsb.grid(row=1, column=0, sticky="ew")
        lf.rowconfigure(0, weight=1); lf.columnconfigure(0, weight=1)
        rf = ttk.Frame(self.paned); self.paned.add(rf, weight=3)
        cols = ("name", "type", "value")
        self.values = ttk.Treeview(rf, columns=cols, show="headings")
        self.values.heading("name", text="Name"); self.values.column("name", width=320)
        self.values.heading("type", text="Type"); self.values.column("type", width=240)
        self.values.heading("value", text="Value"); self.values.column("value", width=380)
        vvsb = ttk.Scrollbar(rf, orient="vertical", command=self.values.yview)
        hhsb = ttk.Scrollbar(rf, orient="horizontal", command=self.values.xview)
        self.values.configure(yscrollcommand=vvsb.set, xscrollcommand=hhsb.set)
        self.values.grid(row=0, column=0, sticky="nsew"); vvsb.grid(row=0, column=1, sticky="ns"); hhsb.grid(row=1, column=0, sticky="ew")
        rf.rowconfigure(0, weight=1); rf.columnconfigure(0, weight=1)
        self.ctx_key_menu = tk.Menu(self, tearoff=False)
        self.ctx_key_menu.add_command(label="New Key", command=self.action_new_key)
        self.ctx_key_menu.add_command(label="New Value", command=self.action_new_value)
        self.ctx_key_menu.add_separator()
        self.ctx_key_menu.add_command(label="Rename", command=self.action_rename)
        self.ctx_key_menu.add_command(label="Delete", command=self.action_delete)
        self.ctx_value_menu = tk.Menu(self, tearoff=False)
        self.ctx_value_menu.add_command(label="Edit Value", command=self.action_edit_value)
        self.ctx_value_menu.add_command(label="Rename Value", command=self.action_rename)
        self.ctx_value_menu.add_command(label="Delete Value", command=self.action_delete)
    def _wire_events(self):
        self.tree.bind("<<TreeviewOpen>>", self.on_tree_open)
        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)
        self.tree.bind("<Button-3>", self.on_tree_right_click)
        self.values.bind("<Double-1>", lambda e: self.action_edit_value())
        self.values.bind("<Return>", lambda e: self.action_edit_value())
        self.values.bind("<Button-3>", self.on_values_right_click)
    def _is_privileged_path(self, path: Path) -> bool:
        abs_path = path.resolve()
        for hive_name in self.privileged_hives:
            hive_path = self.hives.get(hive_name)
            if hive_path and abs_path.is_relative_to(hive_path.resolve()):
                return True
        return False
    def _tree_node_path(self, item_id) -> Path: return Path(self.tree.set(item_id, "path"))
    def refresh_tree(self):
        self.tree.delete(*self.tree.get_children())
        self.values.delete(*self.values.get_children())
        for display_name, path in sorted(self.hives.items()):
            hive_node = self.tree.insert("", "end", text=display_name, image=self.icons.folder, values=(str(path),))
            if path.is_dir():
                try:
                    for child in sorted(path.iterdir()):
                        if child.is_dir():
                            node = self.tree.insert(hive_node, "end", text=child.name, image=self.icons.folder, values=(str(child),))
                            if any(p.is_dir() for p in child.iterdir()): self._set_placeholder(node)
                except PermissionError: pass
            self.tree.item(hive_node, open=True)
    def _set_placeholder(self, item_id):
        for cid in self.tree.get_children(item_id): self.tree.delete(cid)
        self.tree.insert(item_id, "end", text="...", values=("",))
    def _rebuild_children(self, item_id):
        path = self._tree_node_path(item_id)
        self.tree.delete(*self.tree.get_children(item_id))
        try:
            for p in sorted(p for p in path.iterdir() if p.is_dir()):
                node = self.tree.insert(item_id, "end", text=p.name, image=self.icons.folder, values=(str(p),))
                if any(c.is_dir() for c in p.iterdir()): self.tree.insert(node, "end", text="...", values=("",))
        except PermissionError: pass
    def on_tree_open(self, event):
        item = self.tree.focus(); self._rebuild_children(item)
    def on_tree_select(self, event):
        item = self.tree.focus(); self.populate_values(self._tree_node_path(item))
    def populate_values(self, key_path: Path):
        self.values.delete(*self.values.get_children())
        if not key_path.is_dir(): return
        self._ensure_values_tree_has_icon_column()
        try:
            files = [p for p in key_path.iterdir() if p.is_file() and p.name.endswith(VALUE_EXT)]
        except PermissionError: files = []
        for f in sorted(files, key=lambda x: x.name):
            name, vtype = parse_value_filename(f.name)
            if not name: continue
            try: raw_text = f.read_text(encoding="utf-8")
            except Exception: raw_text = ""
            iid = self.values.insert("", "end", values=(name, TYPE_LABELS.get(vtype, vtype), preview_for(vtype, raw_text)))
            self.values.item(iid, image=self.icons.type_icons.get(vtype, ""))
    def _ensure_values_tree_has_icon_column(self):
        if self.values.cget("show") == "tree headings": return
        try:
            self.values.configure(show="tree headings")
            self.values.column("#0", width=28, stretch=False); self.values.heading("#0", text="")
        except tk.TclError: pass
    def on_tree_right_click(self, event):
        iid = self.tree.identify_row(event.y)
        if iid: self.tree.selection_set(iid); self.tree.focus(iid); self.ctx_key_menu.tk_popup(event.x_root, event.y_root)
    def on_values_right_click(self, event):
        iid = self.values.identify_row(event.y)
        if iid: self.values.selection_set(iid); self.values.focus(iid); self.ctx_value_menu.tk_popup(event.x_root, event.y_root)
    def _get_selected_key_path(self) -> Path | None:
        item = self.tree.focus(); return self._tree_node_path(item) if item else None
    def _get_selected_value_parts(self):
        sel = self.values.selection()
        if not sel: return None, None
        name, label, _ = self.values.item(sel[0], "values")
        return name, LABEL_TO_TYPE.get(label, label)
    def action_new_key(self):
        key_path = self._get_selected_key_path()
        if not key_path: messagebox.showwarning("No Key Selected", "Select a key to create a subkey."); return
        name = simpledialog.askstring("New Key", "Enter new key name:", parent=self)
        if not name: return
        new_path = key_path / name
        executor = self._get_executor(key_path)
        try:
            if not executor.mkdir(new_path): return
        except FileExistsError: messagebox.showerror("Error", "A key with that name already exists."); return
        except Exception as e: messagebox.showerror("Error", f"Failed to create key:\n{e}"); return
        parent_item = self.tree.focus()
        if parent_item: self._rebuild_children(parent_item); self.tree.item(parent_item, open=True)
    def action_new_value(self):
        key_path = self._get_selected_key_path()
        if not key_path: messagebox.showwarning("No Key Selected", "Select a key to create a value in."); return
        dlg = ValueEditorDialog(self, "New Value")
        if not dlg.result: return
        name, vtype, normalized = dlg.result
        filename = key_path / f"{name}.{vtype}{VALUE_EXT}"
        if filename.exists(): messagebox.showerror("Error", "A value with that name/type already exists."); return
        executor = self._get_executor(key_path)
        try:
            if not executor.write_text(filename, normalized): return
        except Exception as e: messagebox.showerror("Error", f"Failed to write value:\n{e}"); return
        self.populate_values(key_path)
    def action_edit_value(self):
        key_path = self._get_selected_key_path()
        if not key_path: return
        name, vtype = self._get_selected_value_parts()
        if not name or not vtype: return
        fpath = key_path / f"{name}.{vtype}{VALUE_EXT}"
        try: content = fpath.read_text(encoding="utf-8")
        except Exception: content = ""
        dlg = ValueEditorDialog(self, "Edit Value", initial_name=name, initial_type=vtype, initial_value=deserialize_value(content, vtype))
        if not dlg.result: return
        new_name, new_type, normalized = dlg.result
        target = key_path / f"{new_name}.{new_type}{VALUE_EXT}"
        if target != fpath and target.exists(): messagebox.showerror("Error", "Another value with that name/type already exists."); return
        executor = self._get_executor(key_path)
        try:
            if target != fpath:
                if not executor.write_text(target, normalized): return
                if not executor.unlink(fpath): return
            else:
                if not executor.write_text(target, normalized): return
        except Exception as e: messagebox.showerror("Error", f"Failed to save value:\n{e}"); return
        self.populate_values(key_path)
    def action_rename(self):
        if self.values.focus(): self._rename_value()
        else: self._rename_key()
    def _rename_key(self):
        key_path = self._get_selected_key_path()
        if not key_path or key_path in self.hives.values(): messagebox.showwarning("Invalid", "Select a key to rename (not a hive root)."); return
        new_name = simpledialog.askstring("Rename Key", "New name:", initialvalue=key_path.name, parent=self)
        if not new_name or new_name == key_path.name: return
        target = key_path.parent / new_name
        executor = self._get_executor(key_path)
        try:
            if not executor.rename(key_path, target): return
        except Exception as e: messagebox.showerror("Error", f"Failed to rename key:\n{e}"); return
        parent_item = self.tree.parent(self.tree.focus())
        if parent_item: self._rebuild_children(parent_item); self.tree.item(parent_item, open=True)
        else: self.refresh_tree()
    def _rename_value(self):
        key_path = self._get_selected_key_path(); name, vtype = self._get_selected_value_parts()
        if not all([key_path, name, vtype]): messagebox.showwarning("No Value Selected", "Select a value to rename."); return
        new_name = simpledialog.askstring("Rename Value", "New name:", initialvalue=name, parent=self)
        if not new_name or new_name == name: return
        src = key_path / f"{name}.{vtype}{VALUE_EXT}"; dst = key_path / f"{new_name}.{vtype}{VALUE_EXT}"
        if dst.exists(): messagebox.showerror("Error", "A value with that name/type already exists."); return
        executor = self._get_executor(key_path)
        try:
            if not executor.rename(src, dst): return
        except Exception as e: messagebox.showerror("Error", f"Failed to rename value:\n{e}"); return
        self.populate_values(key_path)
    def action_delete(self):
        if self.values.focus(): self._delete_value()
        else: self._delete_key()
    def _delete_key(self):
        key_path = self._get_selected_key_path()
        if not key_path or key_path in self.hives.values(): messagebox.showwarning("Invalid", "Select a key to delete (not a hive root)."); return
        if not messagebox.askyesno("Confirm Delete", f"Delete key '{key_path.name}' and all its contents?"): return
        executor = self._get_executor(key_path)
        try:
            if not executor.rmtree(key_path): return
        except Exception as e: messagebox.showerror("Error", f"Failed to delete key:\n{e}"); return
        parent_item = self.tree.parent(self.tree.focus()); self._rebuild_children(parent_item)
    def _delete_value(self):
        key_path = self._get_selected_key_path(); name, vtype = self._get_selected_value_parts()
        if not all([key_path, name, vtype]): messagebox.showwarning("No Value Selected", "Select a value to delete."); return
        if not messagebox.askyesno("Confirm Delete", f"Delete value '{name}'?"): return
        executor = self._get_executor(key_path)
        try:
            if not executor.unlink(key_path / f"{name}.{vtype}{VALUE_EXT}"): return
        except Exception as e: messagebox.showerror("Error", f"Failed to delete value:\n{e}"); return
        self.populate_values(key_path)
    def _collect_subtree(self, path: Path):
        tree = {"keys": {}, "values": {}}
        try:
            for f in path.iterdir():
                if f.is_file() and f.name.endswith(VALUE_EXT):
                    name, vtype = parse_value_filename(f.name)
                    if name: tree["values"][name] = {"type": vtype, "data": f.read_text("utf-8")}
            for d in sorted(p for p in path.iterdir() if p.is_dir()):
                tree["keys"][d.name] = self._collect_subtree(d)
        except Exception: pass
        return tree
    def _write_subtree(self, base: Path, tree: dict, executor):
        if isinstance(executor, DirectExecutor): base.mkdir(parents=True, exist_ok=True)
        else: executor.mkdir(base)
        for name, meta in tree.get("values", {}).items():
            executor.write_text(base / f"{name}.{meta.get('type','str')}{VALUE_EXT}", str(meta.get("data", "")))
        for kname, sub in tree.get("keys", {}).items():
            self._write_subtree(base / kname, sub, executor)
    def action_export(self):
        key_path = self._get_selected_key_path()
        if not key_path: messagebox.showwarning("No Key Selected", "Select a key to export."); return
        data = self._collect_subtree(key_path)
        out = filedialog.asksaveasfilename(title="Export Subtree", defaultextension=".json", filetypes=[("JSON", "*.json")])
        if out:
            try:
                with open(out, "w", encoding="utf-8") as f: json.dump({"root": key_path.name, "tree": data}, f, indent=2)
                messagebox.showinfo("Export", "Export completed.")
            except Exception as e: messagebox.showerror("Error", f"Failed to export:\n{e}")
    def _import_or_merge(self, clear_first: bool):
        key_path = self._get_selected_key_path()
        if not key_path: messagebox.showwarning("No Key Selected", "Select a key to import/merge into."); return
        verb = "Import" if clear_first else "Merge"
        inp = filedialog.askopenfilename(title=f"{verb} Subtree", filetypes=[("JSON", "*.json")])
        if not inp: return
        try:
            with open(inp, "r", encoding="utf-8") as f: tree = (json.load(f)).get("tree", {})
        except Exception as e: messagebox.showerror("Error", f"Failed to read JSON:\n{e}"); return
        if clear_first and not messagebox.askyesno("Confirm", f"{verb} will overwrite '{key_path.name}'. Continue?"): return
        executor = self._get_executor(key_path)
        try:
            if clear_first:
                if isinstance(executor, DirectExecutor):
                    shutil.rmtree(key_path)
                else:
                    if not executor.rmtree(key_path): return
            self._write_subtree(key_path, tree, executor)
            messagebox.showinfo(verb, f"{verb} completed.")
        except Exception as e: messagebox.showerror("Error", f"Failed to {verb.lower()}:\n{e}")
        self.populate_values(key_path)
        current_item = self.tree.focus()
        if current_item: self._rebuild_children(current_item)
    def action_import(self): self._import_or_merge(clear_first=True)
    def action_merge(self): self._import_or_merge(clear_first=False)

def main():
    parser = argparse.ArgumentParser(description="AquariusOS Registry Editor")
    parser.add_argument("--hive", action="append", help="Add a standard hive. Format: HKLM:<path>")
    parser.add_argument("--hive-ext", action="append", help="Add custom hive. Format: HKXR:<DisplayName>:<path>")
    args = parser.parse_args()
    is_root = os.geteuid() == 0
    loaded_hives: Dict[str, Path] = {}
    if args.hive_ext:
        for val in args.hive_ext:
            try: _, display_name, path_str = val.split(":", 2)
            except ValueError: print(f"[ERROR] Invalid --hive-ext: '{val}'", file=sys.stderr); continue
            loaded_hives[display_name] = Path(path_str).resolve()
    if args.hive:
        for val in args.hive:
            try: short, path_str = val.split(":", 1)
            except ValueError: print(f"[ERROR] Invalid --hive: '{val}'", file=sys.stderr); continue
            display_name = HIVE_SHORT_MAP.get(short.upper())
            if not display_name: print(f"[ERROR] Unknown hive: '{short}'", file=sys.stderr); continue
            loaded_hives[display_name] = Path(path_str).resolve()
    if not (args.hive or args.hive_ext):
        print("[INFO] No hives specified, loading defaults.", file=sys.stderr)
        loaded_hives = DEFAULT_HIVES.copy()
    final_hives = {}
    for name, path in loaded_hives.items():
        if name == "HKEY_VOLATILE_MEMORY" and not is_root and not os.access(path.parent, os.R_OK | os.X_OK):
            print(f"[WARN] Cannot access '{path}'. Dropping HKVM hive.", file=sys.stderr)
            continue
        if not path.exists():
            print(f"[WARN] Hive path '{path}' does not exist.", file=sys.stderr)
            try:
                path.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                print(f"[ERROR] Cannot create hive path '{path}': {e}", file=sys.stderr)
        final_hives[name] = path
    app = RegistryEditor(final_hives, is_root)
    app.mainloop()

if __name__ == "__main__":
    main()
