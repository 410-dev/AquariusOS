import fnmatch
import json
import sys
import shutil
import os
import subprocess

def load_build_config(config_file: str) -> dict:
    """Load build configuration from a JSON file."""
    with open(config_file, 'r') as f:
        config = json.load(f)

    # Run preprocessor config variables
    uo: dict[str, str] = config.get('PreprocessorConfig', {}).get("Variables", {})
    for key, value in uo.items():
        content = value[4:]
        if value.startswith("RUN:"):
            result = subprocess.run(content, shell=True, capture_output=True, text=True)
            if result.returncode != 0:
                print(f"Error running command for variable {key}: {result.stderr}")
                sys.exit(1)
            config["PreprocessorConfig"]["Variables"][key] = result.stdout.strip()

        elif value.startswith("VAL:"):
            config["PreprocessorConfig"]["Variables"][key] = config[content]

        else:
            config["PreprocessorConfig"]["Variables"][key] = value

    uo2: dict[str, str] = config.get('Packaging', {}).get("Variables", {})
    for key, value in uo2.items():
        content = value[4:]
        if value.startswith("RUN:"):
            result = subprocess.run(content, shell=True, capture_output=True, text=True)
            if result.returncode != 0:
                print(f"Error running command for variable {key}: {result.stderr}")
                sys.exit(1)
            config["Packaging"]["Variables"][key] = result.stdout.strip()

        elif value.startswith("VAL:"):
            config["Packaging"]["Variables"][key] = config[content]

        else:
            config["Packaging"]["Variables"][key] = value

    # For build script command lines, replace {{{VAR}}} with actual values
    packaging_cmdlines: list[list[str]] = config.get("Packaging", {}).get("CommandLines", [])
    for i in range(len(packaging_cmdlines)):
        for j in range(len(packaging_cmdlines[i])):
            cmdline = packaging_cmdlines[i][j]
            new_cmdline = cmdline
            for key, value in config.get('Packaging', {}).get("Variables", {}).items():
                new_cmdline = new_cmdline.replace("{{{" + key + "}}}", value)
            packaging_cmdlines[i][j] = new_cmdline
    config["Packaging"]["CommandLines"] = packaging_cmdlines

    return config


def relocate(target_dir: str, mapping: dict[str, str]) -> None:
    # Rename files and directories in target_dir
    # for item in os.listdir(target_dir):
    #     item_path = os.path.join(target_dir, item)
    #
    #     new_item_name = item
    #     for old, new in mapping.items():
    #         new_item_name = new_item_name.replace(old, new)
    #
    #     new_item_path = os.path.join(target_dir, new_item_name)
    #
    #     if new_item_name != item:
    #         print(f"        Renaming {item_path} to {new_item_path}")
    #         shutil.move(item_path, new_item_path)
    for root, dirs, files in os.walk(target_dir, topdown=False):
        for name in dirs + files:
            item_path = os.path.join(root, name)
            new_name = name
            for old, new in mapping.items():
                new_name = new_name.replace(old, new)
            if new_name != name:
                new_item_path = os.path.join(root, new_name)
                print(f"    Renaming {item_path} to {new_item_path}")
                shutil.move(item_path, new_item_path)


    # Update contents of files in target_dir
    for root, dirs, files in os.walk(target_dir):
        for file in files:
            file_path = os.path.join(root, file)
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            new_content = content
            for old, new in mapping.items():
                new_content = new_content.replace(old, new)
            if new_content != content:
                print(f"    Updating contents of {file_path}")
                with open(file_path, 'w', encoding='utf-8', errors='ignore') as f:
                    f.write(new_content)


def build_project(config: dict) -> None:
    """Build the project based on the provided configuration."""
    print(f"Building project: {config['Name']}")
    print(f"Version: {config['Version']}")
    print(f"Source Directory: {config['Source']}")
    print(f"Cache Directory: {config['Temporary']}")
    print(f"Build Directory: {config['Output']}")

    # Run build steps
    # Create output directory if it doesn't exist
    print("Preparing build...")
    print("Creating output directory...")
    if os.path.isdir(config['Output']):
        print("    Cleaning existing output directory...")
        shutil.rmtree(config['Output'])
    if os.path.isdir(config['Temporary']):
        print("    Cleaning existing temporary directory...")
        shutil.rmtree(config['Temporary'])
    os.makedirs(config['Output'], exist_ok=True)
    os.makedirs(config['Temporary'], exist_ok=True)
    cswd: str = config['Temporary'] + "/step_0" # Current step working directory

    # Copy source files to temporary directory
    print("Copying source files to temporary directory...")
    shutil.copytree(config['Source'], cswd, dirs_exist_ok=True)

    # Run preprocessor
    print("Running preprocessor...")

    # Delete blacklisted files
    print("\n[1/7] [1/4] Removing blacklisted files...")
    blacklist = config.get('PreprocessorConfig', {}).get("BlacklistedFiles", [])
    for root, dirs, files in os.walk(cswd):
        for file in files:
            if file in blacklist:
                file_path = os.path.join(root, file)
                print(f"    Removing blacklisted file: {file_path}")
                os.remove(file_path)

    # For each file in cswd, replace variables
    print("\n[1/7] [2/4] Applying preprocessor variables...")
    # load files to memory
    files: dict[str, str] = {}
    omitting_extensions: list[str] = ["png", "jpg", "jpeg", "gif", "bmp", "tiff", "ico", "svg", "mp4", "mp3", "wav", "flac", "ogg", "zip", "tar", "gz", "bz2", "7z", "xz", "pdf", "docx", "xlsx", "pptx"]
    for root, dirs, fs in os.walk(cswd):
        for file in fs:
            if any(file.lower().endswith("." + ext) for ext in omitting_extensions):
                continue
            file_path = os.path.join(root, file)
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                files[file_path] = f.read()

    for key, value in config.get('PreprocessorConfig', {}).get("Variables", {}).items():
        print("    Replacing {{{" + key + "}}} with " + value)
        for file_path, content in files.items():
            new_content = content
            new_content = new_content.replace("{{{" + key + "}}}", value)
            if new_content != content:
                print(f"        {file_path}")
                files[file_path] = new_content

    # Write back modified files
    for file_path, content in files.items():
        with open(file_path, 'w', encoding='utf-8', errors='ignore') as f:
            f.write(content)

    # Free memory
    files.clear()

    # Perform path replacements
    print("\n[1/7] [3/4] Performing path replacements...")
    relocate(cswd, config.get('PreprocessorConfig', {}).get("PathReplacements", {}))

    # Set executable
    print("\n[1/7] [4/4] Setting executables...")
    for root, dirs, files in os.walk(cswd):
        for file in files:
            # If file name starts with *, then ends with xxx, set as executable
            # If file name ends with *, then starts with xxx, set as executable
            # If file name starts and ends with *, then contains xxx, set as executable
            fnames = config.get('PreprocessorConfig', {}).get("SetExecutables", [])
            for fname in fnames:
                if fname.startswith("*") and fname.endswith("*"):
                    if fname[1:-1] in file:
                        file_path = os.path.join(root, file)
                        print(f"    Setting executable: {file_path}")
                        os.chmod(file_path, 0o755)
                elif fname.startswith("*"):
                    if file.endswith(fname[1:]):
                        file_path = os.path.join(root, file)
                        print(f"    Setting executable: {file_path}")
                        os.chmod(file_path, 0o755)
                elif fname.endswith("*"):
                    if file.startswith(fname[:-1]):
                        file_path = os.path.join(root, file)
                        print(f"    Setting executable: {file_path}")
                        os.chmod(file_path, 0o755)
                elif file == fname:
                    file_path = os.path.join(root, file)
                    print(f"    Setting executable: {file_path}")
                    os.chmod(file_path, 0o755)

    # Perform submodule builds
    print("\n[2/7] Building submodules...")
    # Walk through all directories, see if it contains build.sh and build.json files
    for root, dirs, files in os.walk(cswd):
        if 'build.sh' in files and 'build.json' in files:
            submodule_path = root
            print(f"    Building submodule at: {submodule_path}")
            # Run the build.sh script
            result = subprocess.run(['bash', 'build.sh', 'build.json', config['TargetDistro']], cwd=submodule_path)
            if result.returncode != 0:
                print(f"Error building submodule at {submodule_path}")
                sys.exit(1)

            # Select which one to consider as built output from build.json
            with open(os.path.join(submodule_path, 'build.json'), 'r') as f:
                submodule_build_config = json.load(f)
            output_file = submodule_build_config.get('Output', 'build')

            built_output_path = os.path.join(submodule_path, output_file)
            if not os.path.exists(built_output_path):
                print(f"Built output file {built_output_path} does not exist.")
                sys.exit(1)

            # Copy built output to submodule directory with .out extension
            dest_path = os.path.join(submodule_path, os.path.basename(built_output_path) + '.out')
            print(f"    Moving built output to: {dest_path}")
            os.rename(built_output_path, dest_path)
            print(f"    Removing submodule except for built output: {built_output_path}")
            if os.path.isdir(built_output_path):
                shutil.rmtree(built_output_path)
            if os.path.exists(os.path.join(submodule_path)):
                shutil.rmtree(os.path.join(submodule_path))
            print("    Renaming .out file back to submodule directory")
            os.rename(dest_path, submodule_path)

    # If _overlay directory exists, copy its contents to step 1 dir
    print(f"\n[3/7] Applying overlay if exists...")
    os.makedirs(config['Temporary'] + "/step_1", exist_ok=True)
    for root, dirs, files in os.walk(cswd):
        if '_overlay' in dirs:
            overlay_path = os.path.join(root, '_overlay')
            print(f"    Applying overlay from: {overlay_path} -> {config['Temporary'] + '/step_1'}")
            for item in os.listdir(overlay_path):
                source = os.path.join(overlay_path, item)
                # os.rename(source, config['Temporary'] + '/step_1' + '/' + item)
                if os.path.isdir(source):
                    shutil.copytree(source, config['Temporary'] + '/step_1' + '/' + item, dirs_exist_ok=True)
                else:
                    shutil.copy2(source, config['Temporary'] + '/step_1' + '/' + item)
            print(f"    Removing overlay directory: {overlay_path}")
            shutil.rmtree(overlay_path)

    # Move files by mapping to output directory
    pswd = cswd
    cswd = config['Temporary'] + "/step_1"
    print("\n[4/7] Moving files to assigned output directory...")
    mapping: dict[str, str] = config.get("Mapping", {})
    for src, dest in mapping.items():
        ldest = cswd + "/" + dest
        lsrc = os.path.join(pswd, src)
        print(f"    Moving {lsrc} to {ldest} ({dest})")
        if not os.path.isdir(lsrc):
            print(f"    Source {lsrc} does not exist, skipping...")
            continue
        if not os.path.exists(os.path.dirname(ldest)):
            os.makedirs(os.path.dirname(ldest), exist_ok=True)
        if os.path.isdir(lsrc):
            shutil.copytree(lsrc, ldest, dirs_exist_ok=True)
        else:
            shutil.copy2(lsrc, ldest)

    # Patching
    # Check if any patch files exist in config['Patches']
    print("\n[5/7] Applying patches...")
    patches: dict[str, bool] = config.get("Patches", {})
    for patch_file, enabled in patches.items():
        patch_path = os.path.join('patches', patch_file)
        if enabled:
            print(f"    Applying patch: {patch_path}")
            if os.path.isdir(patch_path):
                shutil.copytree(patch_path, cswd, dirs_exist_ok=True)
            elif os.path.isfile(patch_path):
                # Use patch command to apply the patch
                shutil.copy2(patch_path, cswd)
            else:
                print(f"    Patch file {patch_path} does not exist.")
                sys.exit(1)

        else:
            print(f"    Skipping patch: {patch_path}")

    # Compose maintainer's script
    def compose_maintainer_script(scope: str, distro: str, output: str) -> None:
        distro = distro.lower()
        if distro in ["debian", "ubuntu"]:
            # Scope is any of: preinst, postinst, prerm, postrm
            # Script is expected to be in src/package-meta/{distro}/{scope}.d/xx-xxxxx.sh
            script_path = os.path.join(pswd, "package-meta", distro, scope + ".d")
            if not os.path.isdir(script_path):
                print(f"    No maintainer script directory found for {distro} {scope}, skipping...")
                return
            scripts = [scriptf for scriptf in os.listdir(script_path) if scriptf.endswith(".sh")]
            if not scripts:
                print(f"    No maintainer scripts found in {script_path}, skipping...")
                return
            scripts.sort() # Ensure order by filename (1 to N)
            combined_script_path = os.path.join(output, "DEBIAN", scope)
            print(f"    Composing maintainer script for {distro} {scope} at {combined_script_path}")
            with open(combined_script_path, 'w') as outfile:
                outfile.write("#!/bin/bash\n\n")
                for script in scripts:
                    script_file_path = os.path.join(script_path, script)
                    print(f"    Adding maintainer script: {script_file_path}")
                    with open(script_file_path, 'r') as infile:
                        outfile.write(f"\n# Begin of script {script}\n")
                        script_content = infile.read()
                        # Remove shebang if exists
                        if script_content.startswith("#!"):
                            script_lines = script_content.splitlines()
                            for line in script_lines:
                                if line.startswith("#!"):
                                    continue
                                outfile.write(line + "\n")
                        else:
                            outfile.write(script_content)
                        outfile.write(f"\n# End of script {script}\n")
                        outfile.write("\n\n")
            os.chmod(combined_script_path, 0o755)
            # Remove directory after composing
            shutil.rmtree(combined_script_path + ".d", ignore_errors=True)
        else:
            print(f"    No maintainer script support for distro {distro}, skipping...")
    print("\n[6/7] Composing maintainer scripts...")

    compose_maintainer_script("preinst", config['TargetDistro'], cswd)
    compose_maintainer_script("postinst", config['TargetDistro'], cswd)
    compose_maintainer_script("prerm", config['TargetDistro'], cswd)
    compose_maintainer_script("postrm", config['TargetDistro'], cswd)

    # Packaging
    pswd = cswd
    cswd = config['Temporary'] + "/step_2"
    print("\n[7/7] Packaging the build output...")
    packaging_cmdlines: list[list[str]] = config.get("Packaging", {}).get("CommandLines", [])
    for cmdline in packaging_cmdlines:
        print(f"    Running packaging command: {' '.join(cmdline)}")
        result = subprocess.run(cmdline, cwd=os.getcwd())
        if result.returncode != 0:
            print(f"Error running packaging command: {' '.join(cmdline)}")
            sys.exit(1)

    # Expect any file pattern match
    output_patterns: list[str] = config.get("Packaging", {}).get("OutputPatterns", [])
    for pattern in output_patterns:
        print(f"    Collecting output files matching pattern: {pattern}")
        for root, dirs, files in os.walk(pswd):
            for file in files:
                if fnmatch.fnmatch(file, pattern):
                    print(f"        Found output file: {file} at {root}")
                    print(f"        -> Moving {file} to output directory")
                    src_path = os.path.join(root, file)
                    os.rename(src_path, os.path.join(config['Output'], file))

    print("Build completed successfully.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: build.py <build-config-file>")
        sys.exit(1)

    config_file = sys.argv[1]
    build_config = load_build_config(config_file)
    build_project(build_config)
