import sys
import os

from oscore import libreg as reg
from oscore import libapplog as logger

def main():
    substruct: list[str] = reg.read("HKEY_LOCAL_MACHINE/SYSTEM/Services/Aqua/DirectoryMaker/SubStructure", "features,homes,lib,logs,man,registry,share,sys,services".split(","))
    for dirname in substruct:
        os.makedirs("{{AQUAROOT}}/" + dirname, exist_ok=True)
        logger.info("CREATE: {{AQUAROOT}}/" + dirname)
    logger.info("DirectoryMaker Service Completed.")

if __name__ == "__main__":
    main()
    sys.exit(0)
