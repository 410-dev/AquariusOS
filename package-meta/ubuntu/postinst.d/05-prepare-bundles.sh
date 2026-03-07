#!/bin/bash

for service_bundle in {{SYS_SERVICES}}/*.apprun; do
    if [[ -d "$service_bundle" ]]; then
        /usr/local/sbin/apprun-prepare.sh "$service_bundle"
    fi
done