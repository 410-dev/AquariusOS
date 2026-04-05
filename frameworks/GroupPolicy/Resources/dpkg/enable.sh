#!/bin/bash

set -e
if [[ "$1" == "True" ]] || [[ "$1" == "true" ]]; then
    echo "Enabling..."
    dpkg-divert --divert /usr/bin/dpkg.distrib --rename /usr/bin/dpkg
    chmod +x {{SYS_FRAMEWORKS}}/GroupPolicy/Resources/dpkg/dpkg.sh
    ln -s {{SYS_FRAMEWORKS}}/GroupPolicy/Resources/dpkg/dpkg.sh /usr/bin/dpkg
    chmod +x /usr/bin/dpkg
    echo "OK"
else
    echo "Disabling..."
    rm -f /usr/bin/dpkg
    dpkg-divert --remove --rename /usr/bin/dpkg
    echo "OK"
fi
set +e
