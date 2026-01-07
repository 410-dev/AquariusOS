#!/bin/bash

for service_bundle in /opt/aquariusos/sys/services/*.apprun; do
    if [[ -d "$service_bundle" ]]; then
        /usr/local/sbin/apprun-prepare.sh "$service_bundle"
    fi
done