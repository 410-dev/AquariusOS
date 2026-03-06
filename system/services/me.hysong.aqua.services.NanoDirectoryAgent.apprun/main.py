import sys

from oscore import libreg as reg
from oscore import libapplog as logger

from nanodir.client import request as client_request

def main():

    # Check if directory service is enabled
    enabled: bool = reg.read("HKEY_LOCAL_MACHINE/SYSTEM/ControlSet/Control/GroupEnrollment/Enabled", False)
    if not enabled:
        logger.info("Current machine is not enrolled in NanoDirectory. Exiting NanoDirectoryAgent.")
        return 0

    # Initial request
    client_request.request_policy()

    return 0



if __name__ == "__main__":
    sys.exit(main())
