import sys
import os

import libreg as reg
import libapplog as logger

def main():
    substruct: list[str] = reg.read("HKEY_LOCAL_MACHINE/SYSTEM/Services/me.hysong.aqua.services.DirectoryMaker/SubStructure", "features,homes,lib,logs,man,registry,share,sys,services".split(","))
    for dirname in substruct:
        os.makedirs("/opt/aqua/" + dirname, exist_ok=True)
        logger.info("CREATE: /opt/aqua/" + dirname)
    logger.info("DirectoryMaker Service Completed.")

if __name__ == "__main__":
    main()
    sys.exit(0)
