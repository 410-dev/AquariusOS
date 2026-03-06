import os
import secrets

# def remove_secure(path: str, removalType: int = 0, iteration: int = 1) -> bool:
#     """
#     Securely deletes a file or a directory (recursively) by overwriting content.
#     """
#     if not os.path.exists(path):
#         return False

#     try:
#         if os.path.isdir(path):
#             # Iterate through everything in the directory
#             for root, dirs, files in os.walk(path, topdown=False):
#                 # First, securely wipe all files in the current folder
#                 for name in files:
#                     file_path = os.path.join(root, name)
#                     _wipe_file_logic(file_path, removalType, iteration)
                
#                 # After files are gone, remove the empty subdirectories
#                 for name in dirs:
#                     os.rmdir(os.path.join(root, name))
            
#             # Finally, remove the top-level directory itself
#             os.rmdir(path)
#         else:
#             # If it's just a single file
#             _wipe_file_logic(path, removalType, iteration)

#         return True
#     except Exception as e:
#         print(f"Error during recursive secure deletion: {e}")
#         return False

# def _wipe_file_logic(path: str, removalType: int, iteration: int):
#     """Internal helper to handle the byte-level overwriting."""
#     file_size = os.path.getsize(path)
    
#     with open(path, "ba+", buffering=0) as f:
#         for _ in range(iteration):
#             f.seek(0)
#             if removalType == 0:
#                 f.write(b'\x00' * file_size)
#             elif removalType == 1:
#                 f.write(secrets.token_bytes(file_size))
            
#             f.flush()
#             os.fsync(f.fileno())

#     # Obfuscate metadata and delete
#     random_name = secrets.token_hex(8)
#     new_path = os.path.join(os.path.dirname(path), random_name)
#     os.rename(path, new_path)
#     os.remove(new_path)

BLOCK = 1024 * 1024  # 1 MiB chunks

def wipe_file(path: str, passes: int = 2, random_last: bool = True):
    fd = os.open(path, os.O_RDWR)
    try:
        size = os.lseek(fd, 0, os.SEEK_END)

        for p in range(passes):
            os.lseek(fd, 0, os.SEEK_SET)
            remaining = size

            while remaining > 0:
                chunk = min(BLOCK, remaining)
                if p == passes - 1 and random_last:
                    data = secrets.token_bytes(chunk)
                else:
                    data = b'\x00' if (p % 2 == 0) else b'\xFF'
                    data *= chunk

                os.write(fd, data)
                remaining -= chunk

            os.fsync(fd)

        os.ftruncate(fd, 0)
        os.fsync(fd)

    finally:
        os.close(fd)

    # Rename to random name to destroy directory entry patterns
    dir_fd = os.open(os.path.dirname(path) or ".", os.O_DIRECTORY)
    try:
        new_name = secrets.token_hex(8)
        os.rename(path, os.path.join(os.path.dirname(path), new_name))
        os.unlink(os.path.join(os.path.dirname(path), new_name))
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)



def main(files: list[str], removalType: int = 0, iteration: int = 1) -> bool:
    """
    Main function to securely delete multiple files or directories.
    """
    all_success = True
    for file in files:
        success = wipe_file(file, passes=iteration, random_last=(removalType == 1))
        if not success:
            all_success = False
    return all_success

if __name__ == "__main__":
    import sys
    # Parameters:
    #   --iterations <number>
    #   --type <zero|random>
    #   <file1> <file2> ...

    args = sys.argv[1:]
    iteration = 1
    removalType = 0  # 0 for zero, 1 for random
    files = []
    i = 0
    while i < len(args):
        if args[i] == "--iterations" and i + 1 < len(args):
            iteration = int(args[i + 1])
            i += 2
        elif args[i] == "--type" and i + 1 < len(args):
            if args[i + 1].lower() == "zero":
                removalType = 0
            elif args[i + 1].lower() == "random":
                removalType = 1
            i += 2
        else:
            files.append(args[i])
            i += 1

    success = main(files, removalType, iteration)
    if not success:
        sys.exit(1)
    sys.exit(0)