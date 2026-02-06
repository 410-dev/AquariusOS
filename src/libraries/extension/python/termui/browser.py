#!/usr/bin/env python3
"""
Hierarchical terminal checkbox multi-select (curses).

- Up/Down or k/j to move
- Enter / Right / l to open a container (module -> category -> member)
- Backspace / Left / h / b to go back
- Space to toggle selection (on a leaf), or toggle whole subtree (on a non-leaf)
- s to submit (finish) and print selected paths
- q or Esc to cancel (prints nothing)

Selected path format:
["module>functions>cumulative_return", ...]
"""

import curses
from typing import Any, List, Tuple, Dict, Set

# ---- Helper utilities for tree traversal and selection ----

def __sort_key_name(item: Tuple[str, Any]) -> str:
    return item[0].lower()


def __node_children(node_obj: Any) -> List[Tuple[str, Any]]:
    """
    Given a node object, return list of (child_name, child_obj).
    - Root (dict of modules): children are module keys -> module dicts
    - Module dict (has 'functions'/'classes'): children are category names -> lists
    - Category list: children are strings (leaf)
    """
    if isinstance(node_obj, dict):
        # Root or module dict. If module dict contains 'functions'/'classes' keys, expose them as children.
        # Distinguish root-level dict (mapping module_name -> module_dict) vs a module dict
        # Heuristics: if values are lists with 'functions' and 'classes' keys? We'll detect keys.
        if set(node_obj.keys()) >= {"functions", "classes"} and all(isinstance(node_obj.get(k), list) for k in ("functions", "classes")):
            # module level
            children = []
            if node_obj.get("functions"):
                children.append(("functions", node_obj["functions"]))
            if node_obj.get("classes"):
                children.append(("classes", node_obj["classes"]))
            return children
        else:
            # top-level mapping: module name -> module dict
            items = list(node_obj.items())
            items.sort(key=__sort_key_name)
            return items
    elif isinstance(node_obj, list):
        # category: list of member strings
        return [(name, name) for name in node_obj]
    else:
        # leaf string or unknown type
        return []


def __is_leaf_child(child_obj: Any) -> bool:
    return not isinstance(child_obj, (dict, list))


def __make_path_str(path_components: List[str]) -> str:
    return ">".join(path_components)


def __gather_all_leaf_paths(root_obj: Any, base_path: List[str]) -> List[str]:
    """
    Return list of path strings for all leaf descendants under root_obj, prefixed by base_path.
    """
    leaves: List[str] = []

    def walk(obj: Any, path: List[str]):
        if isinstance(obj, dict):
            # if module dict with functions/classes
            if set(obj.keys()) >= {"functions", "classes"} and all(isinstance(obj.get(k), list) for k in ("functions", "classes")):
                for key in ("functions", "classes"):
                    arr = obj.get(key, [])
                    if arr:
                        walk(arr, path + [key])
            else:
                # root-level mapping -> iterate modules
                for k in sorted(obj.keys(), key=str.lower):
                    walk(obj[k], path + [k])
        elif isinstance(obj, list):
            for item in obj:
                # leaves are the strings inside list -> produce a path
                leaves.append(__make_path_str(path + [item]))
        else:
            # unexpected leaf
            leaves.append(__make_path_str(path + [str(obj)]))

    walk(root_obj, base_path)
    return leaves


# ---- Curses UI ----

# def __checkbox_browser(stdscr, data: Dict[str, Any]) -> List[str]:
#     curses.curs_set(0)
#     stdscr.keypad(True)
#
#     # Stack frames store (node_name, node_obj, children_list (name,obj), current_index, top_index)
#     # Root frame: node_name="" and node_obj=data
#     root_children = __node_children(data)
#     stack: List[Tuple[str, Any, List[Tuple[str, Any]], int, int]] = [("", data, root_children, 0, 0)]
#     selected: Set[str] = set()  # set of path strings like "module>functions>name"
#
#     while True:
#         stdscr.erase()
#         h, w = stdscr.getmaxyx()
#
#         # get current frame
#         node_name, node_obj, children, current, top = stack[-1]
#         # breadcrumb
#         breadcrumb = [frame[0] for frame in stack if frame[0]]
#         breadcrumb_line = " / ".join(breadcrumb) if breadcrumb else "(root)"
#         stdscr.addnstr(0, 0, f"Location: {breadcrumb_line}", w - 1, curses.A_BOLD)
#
#         # check terminal size
#         line_offset = 1
#         usable_rows = h - line_offset - 2  # leave 1 line for instructions
#         if usable_rows < 1:
#             usable_rows = 1
#
#         # adjust top if necessary
#         n = len(children)
#         if current < top:
#             top = current
#         elif current >= top + usable_rows:
#             top = current - usable_rows + 1
#         # update stack top
#         stack[-1] = (node_name, node_obj, children, current, top)
#
#         # Render children
#         for idx in range(top, min(top + usable_rows, n)):
#             name, child_obj = children[idx]
#             global_path = [c[0] for c in stack if c[0]] + [name]
#             # compute checkbox state
#             if __is_leaf_child(child_obj):
#                 # leaf: path is full path
#                 path_str = __make_path_str(global_path)
#                 checked = path_str in selected
#                 checkbox = "[x]" if checked else "[ ]"
#                 label = f" {checkbox} {name}"
#             else:
#                 # non-leaf: determine descendant leaves
#                 leaves = __gather_all_leaf_paths(child_obj, global_path)
#                 if not leaves:
#                     checkbox = "[ ]"
#                 else:
#                     count = sum(1 for p in leaves if p in selected)
#                     if count == 0:
#                         checkbox = "[ ]"
#                     elif count == len(leaves):
#                         checkbox = "[x]"
#                     else:
#                         checkbox = "[~]"  # partial
#                 label = f" {checkbox} {name} ->"
#             attr = curses.A_REVERSE if idx == current else curses.A_NORMAL
#             stdscr.addnstr(line_offset + idx - top, 0, label, w - 1, attr)
#
#         # Instructions
#         instr = "Space: toggle / toggle subtree • Enter/right: open • Backspace/left/b: back • s: submit • q/Esc: cancel"
#         stdscr.addnstr(h - 1, 0, instr, w - 1, curses.A_DIM)
#
#         stdscr.refresh()
#         ch = stdscr.getch()
#
#         if ch in (curses.KEY_UP, ord('k')):
#             current = (current - 1) % max(1, n)
#             stack[-1] = (node_name, node_obj, children, current, top)
#         elif ch in (curses.KEY_DOWN, ord('j')):
#             current = (current + 1) % max(1, n)
#             stack[-1] = (node_name, node_obj, children, current, top)
#         elif ch in (curses.KEY_RIGHT, ord('l'), 10, 13):
#             # Enter / right: drill into non-leaf
#             if n == 0:
#                 continue
#             name, child_obj = children[current]
#             if not __is_leaf_child(child_obj):
#                 child_children = __node_children(child_obj)
#                 # push new frame
#                 stack.append((name, child_obj, child_children, 0, 0))
#             else:
#                 # leaf: treat Enter as toggle as well (toggle single leaf)
#                 path_components = [c[0] for c in stack if c[0]] + [name]
#                 path_str = __make_path_str(path_components)
#                 if path_str in selected:
#                     selected.remove(path_str)
#                 else:
#                     selected.add(path_str)
#         elif ch in (curses.KEY_LEFT, curses.KEY_BACKSPACE, 8, ord('h'), ord('b')):
#             # back
#             if len(stack) > 1:
#                 stack.pop()
#             else:
#                 # at root, do nothing
#                 pass
#         elif ch == ord(' '):
#             # toggle current node (leaf or subtree)
#             if n == 0:
#                 continue
#             name, child_obj = children[current]
#             path_prefix = [c[0] for c in stack if c[0]] + [name]
#             if __is_leaf_child(child_obj):
#                 path_str = __make_path_str(path_prefix)
#                 if path_str in selected:
#                     selected.remove(path_str)
#                 else:
#                     selected.add(path_str)
#             else:
#                 # gather all descendant leaves
#                 leaves = __gather_all_leaf_paths(child_obj, path_prefix)
#                 if not leaves:
#                     # nothing to toggle
#                     pass
#                 else:
#                     all_selected = all(p in selected for p in leaves)
#                     if all_selected:
#                         for p in leaves:
#                             selected.discard(p)
#                     else:
#                         for p in leaves:
#                             selected.add(p)
#         elif ch in (ord('s'), ord('S')):
#             # submit (finish) -> return sorted list
#             return sorted(selected)
#         elif ch in (ord('q'), 27):
#             # cancel
#             return []
#         else:
#             # ignore unknown keys
#             pass
#
#
# def run_browser(data: Dict[str, Any], title: str = "") -> List[str]:
#     selected = curses.wrapper(__checkbox_browser, data)
#     return selected


def __checkbox_browser(stdscr, data: Dict[str, Any], title: str = "") -> List[str]:
    curses.curs_set(0)
    stdscr.keypad(True)

    # Stack frames store (node_name, node_obj, children_list (name,obj), current_index, top_index)
    # Root frame: node_name="" and node_obj=data
    root_children = __node_children(data)
    stack: List[Tuple[str, Any, List[Tuple[str, Any]], int, int]] = [("", data, root_children, 0, 0)]
    selected: Set[str] = set()  # set of path strings like "module>functions>name"

    while True:
        stdscr.erase()
        h, w = stdscr.getmaxyx()

        # get current frame
        node_name, node_obj, children, current, top = stack[-1]

        # Title (line 0)
        if title:
            # center title if it fits, otherwise left-align
            x = max(0, (w - len(title)) // 2)
            stdscr.addnstr(0, x, title, w - x - 1, curses.A_BOLD)
        else:
            # keep an empty line for consistent layout
            stdscr.addnstr(0, 0, " ", w - 1, curses.A_NORMAL)

        # breadcrumb on line 1
        breadcrumb = [frame[0] for frame in stack if frame[0]]
        breadcrumb_line = " / ".join(breadcrumb) if breadcrumb else "(root)"
        stdscr.addnstr(1, 0, f"Location: {breadcrumb_line}", w - 1, curses.A_BOLD)

        # check terminal size
        line_offset = 2  # moved down one line to make room for title + breadcrumb
        usable_rows = h - line_offset - 2  # leave 1 line for instructions
        if usable_rows < 1:
            usable_rows = 1

        # adjust top if necessary
        n = len(children)
        if current < top:
            top = current
        elif current >= top + usable_rows:
            top = current - usable_rows + 1
        # update stack top
        stack[-1] = (node_name, node_obj, children, current, top)

        # Render children
        for idx in range(top, min(top + usable_rows, n)):
            name, child_obj = children[idx]
            global_path = [c[0] for c in stack if c[0]] + [name]
            # compute checkbox state
            if __is_leaf_child(child_obj):
                # leaf: path is full path
                path_str = __make_path_str(global_path)
                checked = path_str in selected
                checkbox = "[x]" if checked else "[ ]"
                label = f" {checkbox} {name}"
            else:
                # non-leaf: determine descendant leaves
                leaves = __gather_all_leaf_paths(child_obj, global_path)
                if not leaves:
                    checkbox = "[ ]"
                else:
                    count = sum(1 for p in leaves if p in selected)
                    if count == 0:
                        checkbox = "[ ]"
                    elif count == len(leaves):
                        checkbox = "[x]"
                    else:
                        checkbox = "[~]"  # partial
                label = f" {checkbox} {name} ->"
            attr = curses.A_REVERSE if idx == current else curses.A_NORMAL
            stdscr.addnstr(line_offset + idx - top, 0, label, w - 1, attr)

        # Instructions
        instr = "Space: toggle / toggle subtree • Enter/right: open • Backspace/left/b: back • s: submit • q/Esc: cancel"
        stdscr.addnstr(h - 1, 0, instr, w - 1, curses.A_DIM)

        stdscr.refresh()
        ch = stdscr.getch()

        if ch in (curses.KEY_UP, ord('k')):
            current = (current - 1) % max(1, n)
            stack[-1] = (node_name, node_obj, children, current, top)
        elif ch in (curses.KEY_DOWN, ord('j')):
            current = (current + 1) % max(1, n)
            stack[-1] = (node_name, node_obj, children, current, top)
        elif ch in (curses.KEY_RIGHT, ord('l'), 10, 13):
            # Enter / right: drill into non-leaf
            if n == 0:
                continue
            name, child_obj = children[current]
            if not __is_leaf_child(child_obj):
                child_children = __node_children(child_obj)
                # push new frame
                stack.append((name, child_obj, child_children, 0, 0))
            else:
                # leaf: treat Enter as toggle as well (toggle single leaf)
                path_components = [c[0] for c in stack if c[0]] + [name]
                path_str = __make_path_str(path_components)
                if path_str in selected:
                    selected.remove(path_str)
                else:
                    selected.add(path_str)
        elif ch in (curses.KEY_LEFT, curses.KEY_BACKSPACE, 8, ord('h'), ord('b')):
            # back
            if len(stack) > 1:
                stack.pop()
            else:
                # at root, do nothing
                pass
        elif ch == ord(' '):
            # toggle current node (leaf or subtree)
            if n == 0:
                continue
            name, child_obj = children[current]
            path_prefix = [c[0] for c in stack if c[0]] + [name]
            if __is_leaf_child(child_obj):
                path_str = __make_path_str(path_prefix)
                if path_str in selected:
                    selected.remove(path_str)
                else:
                    selected.add(path_str)
            else:
                # gather all descendant leaves
                leaves = __gather_all_leaf_paths(child_obj, path_prefix)
                if not leaves:
                    # nothing to toggle
                    pass
                else:
                    all_selected = all(p in selected for p in leaves)
                    if all_selected:
                        for p in leaves:
                            selected.discard(p)
                    else:
                        for p in leaves:
                            selected.add(p)
        elif ch in (ord('s'), ord('S')):
            # submit (finish) -> return sorted list
            return sorted(selected)
        elif ch in (ord('q'), 27):
            # cancel
            return []
        else:
            # ignore unknown keys
            pass


def run_browser(data: Dict[str, Any], title: str = "") -> List[str]:
    # pass title through to the curses UI
    selected = curses.wrapper(__checkbox_browser, data, title)
    return selected
