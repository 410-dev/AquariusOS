#!/bin/bash

for service_bundle in {{SYS_SERVICES}}/*.apprun; do
    if [[ -d "$service_bundle" ]]; then
        /usr/bin/apprun-prepare.sh "$service_bundle"
    fi
done