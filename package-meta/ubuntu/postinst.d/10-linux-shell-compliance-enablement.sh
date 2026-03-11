#!/bin/bash

{{SYS_CMDS}}/reg.sh root install {{RESOURCES}}/nixshcompliance/registry-template.regtree
#/usr/local/sbin/apprun-prepare.sh {{OPT_SERVICES}}/nixshcompliance.apprun # This is enabled by 5-prepare-bundles.sh
#{{SYS_CMDS}}/services.sh enable nixshcompliance
