#!/usr/bin/env python3
import argparse
import json
import os
import shutil
from typing import Dict, Optional, Set, List, Tuple

def load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def parse_debian_control(control_path: str) -> Optional[str]:
    """
    Very simple parser: find 'Depends:' line and return the package name.
    """
    if not os.path.isfile(control_path):
        return None

    with open(control_path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if line.lower().startswith("depends:"):
                return line.split(":", 1)[1].strip()
    return None


def match_pattern(pattern: str, name: str) -> bool:
    """
    Implement simple wildcard semantics:
        '*abc*'  -> contains 'abc'
        '*abc'   -> endswith 'abc'
        'abc*'   -> startswith 'abc'
        '*'      -> everything
    No escaping, no complex globbing.
    """
    if pattern == "*":
        return True

    if "*" not in pattern:
        return pattern == name

    if pattern.startswith("*") and pattern.endswith("*"):
        needle = pattern[1:-1]
        return needle in name

    if pattern.startswith("*"):
        needle = pattern[1:]
        return name.endswith(needle)

    if pattern.endswith("*"):
        needle = pattern[:-1]
        return name.startswith(needle)

    # Fallback – treat as exact if malformed
    return pattern == name


def map_package_name(pkg: str, mapping: Dict[str, str]) -> Optional[str]:
    """
    Map apt package name to RPM name using 'packages-mapping'.

    Precedence:
      1. Exact key match without wildcard.
      2. First wildcard rule that matches.
      3. If nothing matches, return original pkg name.

    If mapped value is "_", return None (skip).
    """
    exact_matches: Dict[str, str] = {}
    wildcard_rules: List[Tuple[str, str]] = []

    for k, v in mapping.items():
        if "*" in k:
            wildcard_rules.append((k, v))
        else:
            exact_matches[k] = v

    # Exact match
    if pkg in exact_matches:
        val = exact_matches[pkg]
        if val == "_":
            return None
        return val

    # Wildcard matches (first match wins)
    for pattern, val in wildcard_rules:
        if match_pattern(pattern, pkg):
            if val == "_":
                return None
            return val

    # Fallback: no mapping → keep original name
    return pkg


def apply_move_mapping(path: str, move_map: Dict[str, str]) -> Optional[str]:
    """
    Apply 'move' mapping for a given absolute path.
    Supports directory structure preservation for patterns ending in '*'.
    """
    # Normalize to absolute-style for matching
    if not path.startswith("/"):
        path = "/" + path

    exact_map: Dict[str, str] = {}
    wildcard_rules: List[Tuple[str, str]] = []

    for k, v in move_map.items():
        if "*" in k:
            wildcard_rules.append((k, v))
        else:
            if not k.startswith("/"):
                exact_map["/" + k] = v
            else:
                exact_map[k] = v

    # 1. Exact path match
    detect_path = path.replace(os.sep, "/")  # Normalize for matching
    if detect_path in exact_map:
        target = exact_map[detect_path]
        if target == "_":
            print("[INFO] Omitting path by configuration:", path)
            return None
        if not target.startswith("/"):
            target = "/" + target
        return target

    # 2. Wildcard rules (first match wins)
    for pattern, target in wildcard_rules:
        if match_pattern(pattern, detect_path):
            if target == "_":
                return None

            # --- START OF FIX ---
            # If this is a directory wildcard (e.g. "/a/b/c/*"), we want to
            # preserve the structure after the wildcard.
            if pattern.endswith("*") and not pattern.startswith("*"):
                # pattern: "/a/b/c/*" -> prefix: "/a/b/c/"
                prefix = pattern[:-1]

                # Double check detect_path starts with prefix to be safe
                if detect_path.startswith(prefix):
                    # Extract the remainder (e.g., "subdir/file.txt")
                    remainder = detect_path[len(prefix):]

                    # Clean up remainder so it joins correctly
                    remainder = remainder.lstrip("/")

                    # Ensure target starts with /
                    target_base = target if target.startswith("/") else "/" + target

                    print("[INFO] Wildcard re-root:", path, "->", os.path.join(target_base, remainder))

                    # Join target base with the remainder
                    return os.path.join(target_base, remainder)
            # --- END OF FIX ---

            # Fallback: if not a trailing wildcard re-root, just return target
            if not target.startswith("/"):
                target = "/" + target
            return target

    # 3. No rules matched → keep original path
    return path




def copy_file(src: str, dst: str) -> None:
    ensure_dir(os.path.dirname(dst))
    shutil.copy2(src, dst)


def resolve_package_root(base_dir: str) -> Optional[str]:
    """
    Determine the actual root of the Debian package.

    Logic:
    1. If base_dir/DEBIAN exists, base_dir is the root.
    2. If base_dir/aisp-submodulepattern exists, read it to find the relative
       path to the real root.
    3. Otherwise, return None.
    """
    # Check 1: Standard structure
    if os.path.isdir(os.path.join(base_dir, "DEBIAN")):
        return base_dir

    # Check 2: Indirection via pattern file
    pattern_file = os.path.join(base_dir, "aisp-submodulepattern")
    if os.path.isfile(pattern_file):
        try:
            with open(pattern_file, "r", encoding="utf-8") as f:
                rel_target = f.read().strip()

            # Resolve the path relative to the directory containing the pattern file
            real_root = os.path.normpath(os.path.join(base_dir, rel_target))

            # Verify the target actually looks like a package
            if os.path.isdir(os.path.join(real_root, "DEBIAN")):
                return real_root
            else:
                print(f"[WARN] Submodule pattern in {base_dir} points to {real_root}, "
                      f"but no DEBIAN directory found there.")
        except Exception as e:
            print(f"[WARN] Failed to read submodule pattern in {base_dir}: {e}")

    return None

def build_overlay_from_src(
    src_dir: str,
    overlay_root: str,
    move_map: Dict[str, str],
    cfg_dir: str
) -> None:
    """
    Walk the src directory, process each package, and populate overlay_root.
    """
    ensure_dir(overlay_root)

    # Each direct subdir of src_dir is treated as a package directory
    for entry in os.scandir(src_dir):
        if not entry.is_dir():
            continue

        pkg_dir = resolve_package_root(entry.path)
        if not pkg_dir:
            continue

        debian_dir = os.path.join(pkg_dir, "DEBIAN")
        if not os.path.isdir(debian_dir):
            # Not a dpkg-style package dir, skip
            continue

        # Walk all non-DEBIAN content
        for root, dirs, files in os.walk(pkg_dir):
            # Skip DEBIAN metadata content
            rel_root = os.path.relpath(root, pkg_dir)
            if rel_root.split(os.sep)[0] == "DEBIAN":
                continue

            for fname in files:
                if fname == ".DS_Store":
                    continue
                src_path = os.path.join(root, fname)
                rel_path = os.path.relpath(src_path, pkg_dir)  # e.g. "usr/local/sbin/test.sh"
                abs_original = "/" + rel_path

                new_abs = apply_move_mapping(abs_original, move_map)
                if new_abs is None:
                    # Skipped by mapping
                    continue

                # Convert absolute dest to overlay path
                dest_rel = new_abs.lstrip("/")  # e.g. "usr/local/bin/test.sh"
                dest_path = os.path.join(overlay_root, dest_rel)

                copy_file(src_path, dest_path)


def apply_fedora_patches(
    overlay_root: str,
    patch_dirs: List[str],
    cfg_dir: str
) -> None:
    """
    Copy fedora-specific patches into overlay_root, overriding existing files.
    patch_dirs may be relative; if so, resolve relative to cfg_dir.
    """
    for p in patch_dirs:
        # if os.path.isabs(p):
        #     patch_dir = p
        # else:
        #     patch_dir = os.path.join(cfg_dir, p)
        patch_dir = p

        if not os.path.isdir(patch_dir):
            print(f"[WARN] Fedora patch directory not found: {patch_dir}")
            continue

        for root, dirs, files in os.walk(patch_dir):
            rel = os.path.relpath(root, patch_dir)
            if rel == ".":
                rel = ""
            for fname in files:
                src_path = os.path.join(root, fname)
                if rel:
                    dest_rel = os.path.join(rel, fname)
                else:
                    dest_rel = fname
                dest_path = os.path.join(overlay_root, dest_rel)
                copy_file(src_path, dest_path)


def collect_required_packages(
    src_dir: str,
    packages_mapping: Dict[str, str]
) -> Set[str]:
    """
    Read DEBIAN/control in each package dir and build the set of mapped RPM names.
    """
    required: Set[str] = set()

    for entry in os.scandir(src_dir):
        if not entry.is_dir():
            continue

        pkg_dir = resolve_package_root(entry.path)
        if not pkg_dir:
            continue

        control_path = os.path.join(pkg_dir, "DEBIAN", "control")
        pkg_name = parse_debian_control(control_path)
        if not pkg_name:
            continue
        
        # Multiple package lines in Depends can be comma-separated.
        pkg_names = [n.strip() for n in pkg_name.split(",")]
        for pkg_name in pkg_names:
            mapped = map_package_name(pkg_name, packages_mapping)
            if mapped is None:
                print(f"[INFO] Dependency omitted by mapping: {pkg_name}")
            else:
                print(f"[INFO] Dependency mapped: {pkg_name} -> {mapped}")
            if mapped is None or mapped.strip() == "":
                continue

            required.add(mapped.strip())

    return required


def create_configured_symlinks(
        overlay_root: str,
        symlinks_map: Dict[str, str]
) -> None:
    """
    Create symlinks in the overlay_root based on config.
    Config format: { "/path/where/link/goes": "/target/path" }

    Example: "/opt/aisp/data": "/var/opt/aisp/data"
    Creates a symlink at <overlay_root>/opt/aisp/data pointing to /var/opt/aisp/data
    """
    for link_path_abs, target_path in symlinks_map.items():
        # 1. Construct the physical path for the link inside the build folder
        # Remove leading '/' to join correctly with overlay_root
        rel_link_path = link_path_abs.lstrip("/")
        full_link_path = os.path.join(overlay_root, rel_link_path)

        # 2. Ensure the parent directory for the link exists
        parent_dir = os.path.dirname(full_link_path)
        ensure_dir(parent_dir)

        # 3. Clean up if something already exists there (e.g. copied from src)
        # We want the symlink to take precedence.
        if os.path.lexists(full_link_path):
            if os.path.isdir(full_link_path) and not os.path.islink(full_link_path):
                shutil.rmtree(full_link_path)
            else:
                os.remove(full_link_path)

        # 4. Create the symlink
        # os.symlink(target, link_name) -> ln -sf target link_name
        # NO, DO NOT USE OS.SYMLINK HERE. Use /usr/lib/tmpfiles.d/xxxx.conf instead.
        # This will do the trick on Silverblue systems during boot.
        try:
            # os.symlink(target_path, full_link_path)
            new_name = link_path_abs.replace("/", "-").lstrip("-") + ".conf"
            if not os.path.isdir(f"{overlay_root}/usr/lib/tmpfiles.d"):
                os.makedirs(f"{overlay_root}/usr/lib/tmpfiles.d", exist_ok=True)
            with open(f"{overlay_root}/usr/lib/tmpfiles.d/{new_name}", "w", encoding="utf-8") as f:
                f.write(f"L {link_path_abs} - - - - {target_path}\n")
            print(f"[INFO] Symlinked: {link_path_abs} -> {target_path}")
        except OSError as e:
            print(f"[ERROR] Failed to symlink {link_path_abs}: {e}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build root filesystem overlay from dpkg-style package trees."
    )
    parser.add_argument(
        "--src-dir",
        default="src",
        help="Path to the src directory containing dpkg-style package trees (default: ./src)"
    )
    parser.add_argument(
        "--config",
        default="makeroot-cfg.json",
        help="Path to makeroot-cfg.json (default: ./makeroot-cfg.json)"
    )
    parser.add_argument(
        "--out-dir",
        default="builds",
        help="Output directory for overlays (default: ./builds)"
    )

    args = parser.parse_args()

    src_dir = os.path.abspath(args.src_dir)
    cfg_path = os.path.abspath(args.config)
    out_dir = os.path.abspath(args.out_dir)
    cfg_dir = os.path.dirname(cfg_path)

    if not os.path.isdir(src_dir):
        raise SystemExit(f"[ERROR] src directory does not exist: {src_dir}")

    if not os.path.isfile(cfg_path):
        raise SystemExit(f"[ERROR] makeroot-cfg.json not found: {cfg_path}")

    config = load_config(cfg_path)
    move_map = config.get("move", {})
    packages_mapping = config.get("packages-mapping", {})
    fedora_patches = config.get("overlay-patches", [])

    symlinks_map = config.get("symlinks", {})
    # Overlay root is configured by out_dir + name from config
    overlay_name = config.get("name", "overlays")
    overlay_root = os.path.join(out_dir, overlay_name)
    ensure_dir(out_dir)
    ensure_dir(overlay_root)

    print(f"[INFO] Building overlay from src: {src_dir}")
    build_overlay_from_src(src_dir, overlay_root, move_map, cfg_dir)

    if fedora_patches:
        print(f"[INFO] Applying overlay-patches: {fedora_patches}")
        apply_fedora_patches(overlay_root, fedora_patches, cfg_dir)

    if symlinks_map:
        print("[INFO] Creating configured symlinks...")
        create_configured_symlinks(overlay_root, symlinks_map)

    print("[INFO] Collecting required packages from DEBIAN/control files...")
    required_packages = collect_required_packages(src_dir, packages_mapping)

    print(f"[INFO] Required packages after mapping: {sorted(required_packages)}")

    # Write package info to a file
    pkg_list_path = os.path.join(out_dir, "required-packages.txt")
    with open(pkg_list_path, "w", encoding="utf-8") as f:
        for pkg in sorted(required_packages):
            f.write(pkg + "\n")

    print("[INFO] Done. Overlay is in:")
    print(f"       {out_dir}")


if __name__ == "__main__":
    main()
